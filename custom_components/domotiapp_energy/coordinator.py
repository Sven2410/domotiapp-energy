"""Driving the calculation engine from Home Assistant (SPEC.md §18).

The coordinator owns *when* a calculation happens; the engine owns what comes
out of it. Nothing here polls: a recalculation is triggered by a state change
of an explicitly linked entity, by an explicit user action, or by the five
minute safety interval that catches an entity which stopped reporting.

Four rules keep that from becoming expensive or racy:

* the state listener covers **only** the entity ids the installer linked
  themselves, never everything in Home Assistant (SPEC.md §2.1);
* it is rebuilt whenever the configuration changes, so a newly linked entity is
  picked up and a removed one stops waking us;
* triggers are debounced, so a burst of state changes costs one calculation;
* a lock keeps two calculations from overlapping.

Every subscription is handed to ``entry.async_on_unload``, so a reload leaves
nothing behind.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    LOG_EVENT_ADVICE_RECALCULATED,
    LOG_EVENT_PEAK_RISK_DETECTED,
    LOG_EVENT_SOLAR_SURPLUS_DETECTED,
    PEAK_RISK_RELEASE_MARGIN_PERCENT,
    PRIMARY_ADVICE_MIN_DWELL_SECONDS,
    RECALCULATE_DEBOUNCE_SECONDS,
    SAFETY_RECALCULATE_INTERVAL_MINUTES,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SOLAR_SURPLUS_RELEASE_FRACTION,
)
from .engine.advisor import Advisor, advice_rank
from .engine.calculator import Calculator
from .engine.hysteresis import Latch, PrimaryAdviceGate
from .engine.providers import CoachProvider
from .models import CoachResult, EnergyMetrics, StoredConfiguration
from .storage import ConfigurationStore

_LOGGER = logging.getLogger(__name__)

# Logbook subjects for the events the engine itself produces. Fixed strings, so
# the anti-spam rule in the store collapses repeats of the same finding instead
# of writing a line per recalculation (SPEC.md §8).
_SUBJECT_PEAK_RISK = "metrics:peak_risk"
_SUBJECT_SOLAR_SURPLUS = "metrics:solar_surplus"
_SUBJECT_RECALCULATED = "coach:recalculated"


@dataclass(slots=True)
class DomotiAppEnergyData:
    """What one loaded config entry keeps in ``entry.runtime_data``.

    SPEC.md §0 requires ``entry.runtime_data`` rather than ``hass.data``, so
    this is the only place the per-entry objects live.
    """

    store: ConfigurationStore
    coordinator: EnergyCoordinator


# The typed config entry every module in this integration annotates against.
type DomotiAppEnergyConfigEntry = ConfigEntry[DomotiAppEnergyData]


def tracked_entity_ids(config: StoredConfiguration) -> set[str]:
    """Return every entity id the installer linked explicitly.

    This is the complete input the integration reads, and therefore exactly
    what the state listener has to cover. Nothing is discovered, matched by
    name or inferred from a device (SPEC.md §2.1); a row that the engine will
    not use contributes nothing to watch.
    """
    entity_ids: set[str] = set()

    for source in config.sources:
        if not source.is_usable:
            continue
        for entity_id in (
            source.binding.entity_id,
            source.import_entity_id,
            source.export_entity_id,
        ):
            if entity_id:
                entity_ids.add(entity_id)

    for device in config.devices:
        if device.is_usable:
            entity_ids.update(device.entity_links.values())

    return entity_ids


class EnergyCoordinator(DataUpdateCoordinator[CoachResult]):
    """Recalculates the coach result and hands it to the entities.

    ``update_interval`` stays ``None``: there is nothing to poll. The engine,
    the advisor and the coach provider are injected, so the coordinator can be
    exercised without Home Assistant deciding which of them it gets
    (SPEC.md §17).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        store: ConfigurationStore,
        provider: CoachProvider,
    ) -> None:
        """Set up the coordinator without subscribing to anything yet."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=RECALCULATE_DEBOUNCE_SECONDS,
                immediate=False,
            ),
        )
        self._entry = entry
        self._store = store
        self._calculator = Calculator(hass)
        self._advisor = Advisor()
        self._provider = provider
        # One calculation at a time. Two overlapping runs would read the same
        # states twice and race each other into the entities.
        self._calculation_lock = asyncio.Lock()
        self._unsub_states: CALLBACK_TYPE | None = None
        # Everything that has to remember the previous answer lives here, so the
        # calculator and the advisor stay pure functions of their input
        # (engine/hysteresis.py). A configuration change resets all three: the
        # thresholds they were holding an answer against no longer apply.
        self._peak_latch = Latch()
        self._surplus_latch = Latch()
        self._advice_gate = PrimaryAdviceGate(
            minimum_seconds=PRIMARY_ADVICE_MIN_DWELL_SECONDS
        )

    @callback
    def async_start(self) -> None:
        """Subscribe to everything this coordinator needs, and clean up later.

        Called once from ``async_setup_entry``. Every subscription is
        registered with the entry, so unloading or reloading the integration
        takes them all down (SPEC.md §18).
        """
        entry = self._entry

        self.async_rebuild_state_listener()
        entry.async_on_unload(self._async_stop_state_listener)
        entry.async_on_unload(
            self._store.add_change_listener(self._handle_configuration_change)
        )
        entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._handle_safety_interval,
                timedelta(minutes=SAFETY_RECALCULATE_INTERVAL_MINUTES),
                name=f"{DOMAIN} safety recalculation",
            )
        )

    @callback
    def async_rebuild_state_listener(self) -> None:
        """Listen to the currently linked entities, and only to those.

        The old subscription is dropped first: keeping it would leave the
        integration waking up for an entity the installer just unlinked.
        """
        self._async_stop_state_listener()

        entity_ids = tracked_entity_ids(self._store.config)
        if not entity_ids:
            # Nothing linked yet. The safety interval still runs, so the entities
            # keep reflecting the configuration.
            _LOGGER.debug("No linked entities to watch")
            return

        _LOGGER.debug("Watching %s linked entities", len(entity_ids))
        self._unsub_states = async_track_state_change_event(
            self.hass,
            sorted(entity_ids),
            self._handle_tracked_state_event,
        )

    @callback
    def _async_stop_state_listener(self) -> None:
        """Unsubscribe from the entities currently being watched."""
        if self._unsub_states is not None:
            self._unsub_states()
            self._unsub_states = None

    async def async_recalculate(self) -> None:
        """Recalculate right now, at the explicit request of a user.

        Skips the debouncer, because the user is waiting for the result, and
        records it in the logbook so the panel can show that it happened.
        """
        await self.async_refresh()
        await self._store.async_add_log_entry(
            LOG_EVENT_ADVICE_RECALCULATED,
            "Advies opnieuw berekend",
            "Het energieadvies is opnieuw berekend.",
            subject=_SUBJECT_RECALCULATED,
        )

    # --- Triggers -----------------------------------------------------------

    async def _handle_tracked_state_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Recalculate after a linked entity changed, debounced."""
        _LOGGER.debug("Linked entity %s changed", event.data["entity_id"])
        await self.async_request_refresh()

    async def _handle_safety_interval(self, _now: object) -> None:
        """Recalculate periodically, so a stale reading cannot go unnoticed.

        An entity that silently stops updating produces no state event at all;
        without this the panel would keep showing the last calculation as if it
        were current (SPEC.md §18).
        """
        await self.async_refresh()

    @callback
    def _handle_configuration_change(self) -> None:
        """React to a configuration change: rewatch, then recalculate.

        Runs while the store holds its write lock, so it only schedules work.

        The latches are cleared as well. They hold an answer against a threshold
        that has just been edited, and carrying that answer over would mean the
        first result after a change still reflected the old setting.
        """
        self._peak_latch.reset()
        self._surplus_latch.reset()
        self._advice_gate.reset()
        self.async_rebuild_state_listener()
        self._entry.async_create_background_task(
            self.hass,
            self.async_request_refresh(),
            name=f"{DOMAIN} recalculate after configuration change",
        )

    # --- Calculation --------------------------------------------------------

    async def _async_update_data(self) -> CoachResult:
        """Read the sources, derive the metrics and phrase the advice."""
        async with self._calculation_lock:
            config = self._store.config

            # Read first, then report: the snapshot is what knows which sources
            # went quiet. Reporting here rather than at load time keeps the
            # storage read side free of writes (SPEC.md §13), and it is the
            # moment the quarantined rows become functionally relevant — the
            # engine is about to skip them.
            snapshot = self._calculator.build_snapshot(config)
            await self._store.async_report_invalid_rows(snapshot.source_failures)

            metrics = self._calculator.derive_metrics(config, snapshot)
            self._apply_hysteresis(config, metrics)

            advice = self._advisor.generate(config, metrics)
            advice = self._advice_gate.choose(
                advice, now=dt_util.utcnow(), rank_of=advice_rank
            )
            result = CoachResult(
                primary_advice=advice[0] if advice else None,
                advice=advice,
                metrics=metrics,
            )
            result = await self._provider.async_generate(result)

            await self._async_log_findings(config, metrics)
            return result

    def _apply_hysteresis(
        self, config: StoredConfiguration, metrics: EnergyMetrics
    ) -> None:
        """Let the previous answer hold where the reading hovers on a threshold.

        The calculator produced the plain comparisons; this replaces them with
        the latched ones. Both thresholds keep their configured switch-on point
        and gain a release point below it, so a load sitting at 79-81% of the
        maximum, or a surplus drifting either side of ``min_solar_surplus_w``,
        no longer turns an answer on and off every few seconds (SPEC.md §16).
        """
        warning_percent = float(config.home.peak_warning_percent)
        metrics.peak_risk = self._peak_latch.update(
            metrics.grid_load_percent,
            on_at=warning_percent,
            off_at=warning_percent - PEAK_RISK_RELEASE_MARGIN_PERCENT,
        )

        minimum = config.home.min_solar_surplus_w
        metrics.solar_surplus_sufficient = self._surplus_latch.update(
            metrics.solar_surplus_w,
            on_at=minimum,
            off_at=minimum * SOLAR_SURPLUS_RELEASE_FRACTION,
        )

    async def _async_log_findings(
        self, config: StoredConfiguration, metrics: EnergyMetrics
    ) -> None:
        """Record the two situations SPEC.md §8 wants in the logbook.

        Both carry a fixed subject, so a situation that persists across many
        recalculations collapses into one line with a counter instead of
        flooding the logbook.
        """
        if metrics.peak_risk and metrics.grid_load_percent is not None:
            # The verb follows the direction of the flow: the fuse limits both,
            # but a home that is exporting is not "using" its maximum
            # (SPEC.md §16).
            exporting = metrics.grid_power_w is not None and metrics.grid_power_w < 0
            direction = "levert terug met" if exporting else "gebruikt"
            await self._store.async_add_log_entry(
                LOG_EVENT_PEAK_RISK_DETECTED,
                "Piekbelasting gesignaleerd",
                f"De woning {direction} {metrics.grid_load_percent:.0f}% van het "
                f"ingestelde maximale netvermogen. Dat ligt op of boven de "
                f"waarschuwingsgrens van {config.home.peak_warning_percent}%.",
                severity=SEVERITY_WARNING,
                subject=_SUBJECT_PEAK_RISK,
            )

        surplus = metrics.solar_surplus_w
        # The latched answer, not the raw comparison: the logbook would
        # otherwise keep bumping its counter every time the surplus crossed the
        # threshold, which is the write the flapping used to pay for.
        if (
            metrics.solar_surplus_sufficient
            and surplus is not None
            and (config.home.min_solar_surplus_w > 0)
        ):
            await self._store.async_add_log_entry(
                LOG_EVENT_SOLAR_SURPLUS_DETECTED,
                "Zonneoverschot beschikbaar",
                f"Er is {surplus:.0f} W zonneoverschot beschikbaar.",
                severity=SEVERITY_INFO,
                subject=_SUBJECT_SOLAR_SURPLUS,
            )
