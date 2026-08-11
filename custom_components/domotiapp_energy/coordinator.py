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
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
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
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DEVICE_LINK_POWER,
    DEVICE_RUNNING_MIN_POWER_W,
    DOMAIN,
    LOG_EVENT_ADVICE_RECALCULATED,
    LOG_EVENT_PEAK_RISK_DETECTED,
    LOG_EVENT_SOLAR_SURPLUS_DETECTED,
    PEAK_RISK_RELEASE_MARGIN_PERCENT,
    PRIMARY_ADVICE_MIN_DWELL_SECONDS,
    READY_DONE_BINDINGS,
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
from .models import CoachResult, EnergyMetrics, ReadyFlag, StoredConfiguration
from .runtime_store import (
    RuntimeStore,
    can_see_finished,
    expires_at,
    is_finished_state,
)
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
    # The ready flags, in their own store because they are state and not
    # configuration: they clear themselves, and a write there would raise the
    # revision under an open form (SPEC.md §32.5).
    runtime: RuntimeStore
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
        runtime: RuntimeStore,
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
        self._runtime = runtime
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
        # The lowest running power seen per appliance, with the entity it was
        # seen on (SPEC.md §59.3). Memory only, by the same rule as the latches
        # above — derived state never goes back to the store — so it starts
        # empty after a restart and the panel says so.
        #
        # **Not reset by a configuration change**, and that is the difference
        # with the latches: they hold an answer against a threshold somebody
        # just edited, while this holds a measurement, which no edit can make
        # untrue. The one edit that does invalidate it is a different power
        # entity, and that is why the entity travels with the figure.
        self._lowest_running_power: dict[str, tuple[str, float]] = {}

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
        # **De eerste echte meting, zodra alles er is** (SPEC.md §63). De
        # berekening bij het opzetten blijft staan — anders hebben onze
        # entiteiten uren geen waarde bij een HA die traag start — maar zij
        # leest een wereld die nog niet af is. `async_at_started` vuurt
        # onmiddellijk wanneer HA al draait, dus een herlaadbeurt van de
        # integratie kost hooguit één extra berekening; de debouncer vangt de
        # samenloop met de eerste.
        entry.async_on_unload(async_at_started(self.hass, self._handle_started))
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

    async def _handle_started(self, _hass: HomeAssistant) -> None:
        """Herbereken zodra Home Assistant klaar is met opstarten.

        Dit is het moment waarop de bronnen van een klant bestaan. De uitkomst
        van de berekening tijdens het opzetten is per definitie voorlopig: zij
        leest wat er op dat moment toevallig al geregistreerd was.
        """
        _LOGGER.debug("Home Assistant has started: recalculating")
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
        # A flag whose appliance was deleted can never be cleared by the
        # resident and never expires anywhere anyone can see, so it would sit
        # in the file forever. Scheduled rather than awaited: this callback runs
        # while the configuration store holds its write lock.
        self._entry.async_create_background_task(
            self.hass,
            self._runtime.async_forget(
                {device.id for device in self._store.config.devices}
            ),
            name=f"{DOMAIN} forget ready flags of deleted appliances",
        )
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
            # **Niet melden zolang Home Assistant nog opstart** (SPEC.md §63).
            #
            # Wij worden opgezet zodra onze eigen afhankelijkheden klaar zijn,
            # en dat kan ruim vóór de integraties die de bronnen leveren: HA
            # zet ze parallel op. Op dat moment bestaan `sensor.solaredge_…` en
            # zijn buren nog niet, dus alle bronnen falen tegelijk — feitelijk
            # juist en praktisch onzin, want een seconde later bestaan ze wel.
            #
            # Een klant kreeg zo bij elke update drie waarschuwingen die niets
            # betekenden, en dat is erger dan ruis: het leert hem
            # waarschuwingen negeren (dezelfde afweging als §43.2).
            #
            # Een leesfout is dus pas een uitspraak over de installatie zodra
            # de installatie er helemaal is. Tot dan alleen naar het debuglog,
            # waar hij een ontwikkelaar wel iets zegt.
            if self.hass.state is CoreState.running:
                await self._store.async_report_invalid_rows(snapshot.source_failures)
            elif snapshot.source_failures:
                _LOGGER.debug(
                    "Not reporting %s source failures yet: Home Assistant is %s",
                    len(snapshot.source_failures),
                    self.hass.state,
                )

            # Before the advice, because a programme that has just finished
            # must not produce one more "start nu" (SPEC.md §32.6).
            await self._async_clear_finished_flags(config)

            metrics = self._calculator.derive_metrics(config, snapshot)
            self._apply_hysteresis(config, metrics)
            self._track_lowest_running_power(config, metrics)

            advice = self._advisor.generate(
                config, metrics, self._ready_device_ids(config)
            )
            advice = self._advice_gate.choose(
                advice, now=dt_util.utcnow(), rank_of=advice_rank
            )
            result = CoachResult(
                primary_advice=advice[0] if advice else None,
                advice=advice,
                metrics=metrics,
                ready_devices=self._ready_flags(config),
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

    async def _async_clear_finished_flags(self, config: StoredConfiguration) -> None:
        """Take the flag off every appliance that has finished (SPEC.md §32.6).

        **Edge-triggered by the reading, not by a timer.** The check is "does
        this entity say the programme is over", and an appliance that has been
        idle all along never had a flag to clear — the resident sets it while
        the machine is off, so a plain "is it off" test would take it straight
        back off again. What makes that safe here is that the flag is only
        cleared when the *linked* entity says finished, and until the machine
        has actually run its status says something else.

        Two of the three methods §32.6 lists, in its order of reliability, and
        the third is deliberately absent: a power threshold cannot tell a
        dishwasher between wash and dry from one that is done, and clearing a
        flag halfway leaves the resident pressing the button again with no idea
        why. It would buy almost nothing, because the flag already expires at
        the end of the ready window it belongs to.
        """
        for device in config.devices:
            if self._runtime.set_at(device.id) is None:
                continue
            for key in READY_DONE_BINDINGS:
                entity_id = device.entity_links.get(key)
                if not entity_id:
                    continue
                state = self._hass.states.get(entity_id)
                if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    continue
                if is_finished_state(state.state):
                    _LOGGER.debug(
                        "Clearing ready flag for %r: %s reports %r",
                        device.id,
                        entity_id,
                        state.state,
                    )
                    await self._runtime.async_set_ready(device.id, False)
                # The first binding that can answer decides, however it
                # answered. Falling through to a lesser one would let a
                # remaining time of 0 overrule a status that says "washing".
                break

    def _ready_flags(self, config: StoredConfiguration) -> dict[str, ReadyFlag]:
        """Return what the panel needs to phrase one sentence per flag."""
        flags: dict[str, ReadyFlag] = {}
        for device in config.devices:
            set_at = self._runtime.set_at(device.id)
            if set_at is None or not self._runtime.is_ready(device):
                continue
            flags[device.id] = ReadyFlag(
                set_at=set_at,
                expires_at=expires_at(device, set_at),
                auto_clears=can_see_finished(device),
            )
        return flags

    def _ready_device_ids(self, config: StoredConfiguration) -> frozenset[str]:
        """Return the appliances a resident has said there is work in.

        Expiry is asked here, at the moment the advice is made, rather than
        cleared by a timer somewhere: a flag stops meaning anything at a
        moment, not when something happens to run (SPEC.md §32.6). That also
        makes a restart harmless — a flag set yesterday evening is simply no
        longer true this evening, whether or not Home Assistant was up.
        """
        return frozenset(
            device.id for device in config.devices if self._runtime.is_ready(device)
        )

    def _track_lowest_running_power(
        self, config: StoredConfiguration, metrics: EnergyMetrics
    ) -> None:
        """Remember the lowest power each appliance has been seen running at.

        **The only figure that can show an entered `min_power_w` is too high**
        (SPEC.md §59.3). That number describes the car rather than the charger,
        so nobody can reason it out — Sven filled in 1380 W for a car that turned
        out to charge on three phases, and nothing in the product could say so.

        The reverse of the derivation that was considered and rejected: dividing
        power by current would give the number of phases, but only if the current
        sensor reports per phase rather than the sum, and nothing in the value
        says which it is. That assumption fails silently in the harmful
        direction. This comparison needs no second entity at all.

        It catches exactly one of the two mistakes, and it is the invisible one:

        - **too high** — the advice never comes, and silence looks like "no
          surplus". A charging power below the entered minimum proves it.
        - **too low** — the charger draws *more* than the minimum, which is
          indistinguishable from a car charging harder on purpose. Not caught,
          and no measurement can.

        Running is `DEVICE_RUNNING_MIN_POWER_W`, the same floor the overview
        counts appliances by. A second threshold here would be a second answer
        to "is this thing on" (SPEC.md §59.3), and the two would drift.

        **The assumption this rests on, per SPEC.md §47:** the linked sensor
        measures what the appliance draws, and reports near zero when it is
        idle. That holds for a charger's own charging-power sensor, which is the
        one §57.3 sends the installer to; a sensor that also carries the box's
        standby will show that standby here. Which is why this figure is only
        ever *shown*, never compared against and never used in a sum.
        """
        remembered: dict[str, tuple[str, float]] = {}
        for device in config.devices:
            entity_id = device.entity_links.get(DEVICE_LINK_POWER)
            if not entity_id:
                continue

            seen = self._lowest_running_power.get(device.id)
            # A different entity is a different measurement. Carrying the old
            # figure over would attribute one sensor's reading to another, and
            # nothing downstream could tell. Deleting an appliance and its
            # observation together is the same rule one step further.
            if seen is not None and seen[0] != entity_id:
                seen = None

            power = metrics.device_power_w.get(device.id)
            if (
                power is not None
                and power >= DEVICE_RUNNING_MIN_POWER_W
                and (seen is None or power < seen[1])
            ):
                seen = (entity_id, power)

            if seen is not None:
                remembered[device.id] = seen

        self._lowest_running_power = remembered
        metrics.device_power_lowest_w = {
            device_id: power for device_id, (_entity, power) in remembered.items()
        }

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
