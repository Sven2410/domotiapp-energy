"""Gisteren in drie feiten, uit wat Home Assistant al bewaarde (SPEC.md §61).

**Geen eigen opslag.** Onze vijf meetsensoren dragen `state_class`, dus de
recorder houdt er uurstatistieken van bij, en die overleven `purge_keep_days` —
geverifieerd in de bron van 2026.8.1: `recorder/purge.py` raakt de tabel
`statistics` niet aan, alleen `statistics_short_term`. Wat fijner is dan een uur
bestaat alleen binnen het purgevenster, en daar bouwt dit dus niets op.

**Drie feiten, en dat is een grens en geen richtlijn** (SPEC.md §61.4). Elk moet
los verdedigbaar zijn, en elk zegt met opzet minder dan een klant zou willen:

- *hoeveel uur er zonneoverschot was* — niet dat hij het gebruikt heeft;
- *hoe zwaar het net het hoogst belast was* — niet dat dat gevaarlijk was;
- *of de installatie de hele dag compleet was* — niet dat het advies goed was.

**Wat hier bewust niet staat is een dagelijkse zelfbenutting.** Het gemiddelde
van een verhouding is niet de verhouding van de sommen: een ochtenduur met 200 W
opwek waarvan je alles gebruikt telt in zo'n gemiddelde even zwaar als een
middaguur met 4 kW waarvan je de helft terugleverde. Het getal valt daardoor
structureel te hoog uit voor precies de woning die het meest te winnen heeft, en
het oogt in elke test volkomen plausibel (SPEC.md §61.3). De juiste dagwaarde
vraagt om kWh, en die heeft het Energie-dashboard van Home Assistant al.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.domotiapp_energy.const import (
    DOMAIN,
    ENTITY_KEY_DATA_QUALITY,
    ENTITY_KEY_GRID_POWER,
    ENTITY_KEY_SOLAR_SURPLUS,
    ENTITY_OBJECT_ID_NAMES,
    PERCENT_MAX,
)
from custom_components.domotiapp_energy.models import StoredConfiguration

_LOGGER = logging.getLogger(__name__)

_RECORDER = "recorder"


@dataclass(slots=True)
class DayHistory:
    """Wat er gisteren te zien was, in getallen zonder oordeel.

    Elk veld mag ``None`` zijn, en dat betekent hier altijd hetzelfde: die
    statistiek is er niet. Een verse installatie, een uitgeschakelde recorder of
    een sensor die de hele dag niets kon meten zien er in de opslag identiek
    uit, en geen van drieën is een fout die dit overzicht moet melden.
    """

    date: str
    surplus_hours: int | None = None
    peak_grid_power_w: float | None = None
    peak_grid_load_percent: float | None = None
    complete_all_day: bool | None = None
    # Over hoeveel uur van de dag er überhaupt iets is vastgelegd. **Gevonden in
    # de browser**, op een instance die gisteren maar zeven uur aan stond: zes
    # uur zonneoverschot "gisteren" is iets anders wanneer er van die dag maar
    # zeven uur bekend is. Home Assistant staat bij een klant meestal dag en
    # nacht aan — meestal, en dat is precies het soort aanname dat dit project
    # niet stilzwijgend maakt (SPEC.md §47).
    hours_recorded: int = 0
    # Waar of onwaar: is er überhaupt iets vastgelegd over deze dag. Het paneel
    # zegt daarmee "nog geen geschiedenis" in plaats van drie lege regels.
    has_data: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Geef de dag als een JSON-serialiseerbare mapping."""
        return {
            "date": self.date,
            "surplus_hours": self.surplus_hours,
            "peak_grid_power_w": self.peak_grid_power_w,
            "peak_grid_load_percent": self.peak_grid_load_percent,
            "complete_all_day": self.complete_all_day,
            "hours_recorded": self.hours_recorded,
            "has_data": self.has_data,
        }


@dataclass(slots=True)
class _Rows:
    """De uurrijen per statistiek, leeg wanneer er niets is."""

    by_id: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def values(self, key: str, kind: str) -> list[float]:
        """Geef elke uurwaarde van deze soort, zonder de gaten."""
        rows = self.by_id.get(statistic_id(key), [])
        return [float(row[kind]) for row in rows if row.get(kind) is not None]


def statistic_id(entity_key: str) -> str:
    """Geef de statistiek-id van een van onze sensoren.

    Die is gelijk aan de entity-id, en die is Engels en vast (CLAUDE.md regel
    11). Precies dáárom kan hier een geschiedenis op gebouwd worden: een
    Nederlandse installatie draagt dezelfde id als een Engelse.
    """
    name = ENTITY_OBJECT_ID_NAMES[entity_key].lower().replace(" ", "_")
    return f"sensor.{DOMAIN}_{name}"


def yesterday_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Geef begin en eind van gisteren, in de tijdzone van de woning.

    In lokale tijd en niet in UTC, omdat "gisteren" een uitspraak van de bewoner
    is en niet van de klok van de server — dezelfde keuze als bij elk venster in
    deze motor (SPEC.md §16).
    """
    local_now = dt_util.as_local(now)
    start_of_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = start_of_today - timedelta(days=1)
    return dt_util.as_utc(start), dt_util.as_utc(start_of_today)


async def async_yesterday(
    hass: HomeAssistant, config: StoredConfiguration
) -> DayHistory:
    """Vat gisteren samen, of geef een lege dag terug.

    **Nooit een fout.** Zonder recorder, zonder statistieken of met een halve dag
    is het antwoord "hier is nog niets", en dat is een geldige uitkomst: een
    woning die vanmorgen is opgeleverd hoort geen storing te zien omdat zij
    gisteren nog niet bestond.
    """
    start, end = yesterday_bounds(dt_util.utcnow())
    day = DayHistory(date=dt_util.as_local(start).date().isoformat())

    rows = await _async_read_hours(hass, start, end)
    if not rows.by_id:
        return day

    day.has_data = True
    day.hours_recorded = _hours_recorded(rows)
    day.surplus_hours = _surplus_hours(rows, config)
    day.peak_grid_power_w, day.peak_grid_load_percent = _peak_load(rows, config)
    day.complete_all_day = _complete_all_day(rows)
    return day


async def _async_read_hours(
    hass: HomeAssistant, start: datetime, end: datetime
) -> _Rows:
    """Lees de uurstatistieken van de drie sensoren die dit overzicht gebruikt.

    Via de executor van de recorder, want `statistics_during_period` opent een
    databasesessie en hoort dus niet op de eventloop — nagelezen in de bron en
    niet in de documentatie.
    """
    if _RECORDER not in hass.config.components:
        # Een woning kan de recorder uitgeschakeld hebben. Dat is een keuze van
        # de eigenaar en geen storing, dus er wordt niets gemeld.
        _LOGGER.debug("No recorder: skipping the day summary")
        return _Rows()

    # **Binnen de functie, en dat is de bedoeling.** De recorder is een
    # optionele integratie: hem bovenaan importeren zou dit bestand — en
    # daarmee de hele integratie — laten struikelen op een woning die hem
    # uitgeschakeld heeft. Pas hier is bekend dat hij geladen is.
    from homeassistant.components.recorder import get_instance  # noqa: PLC0415
    from homeassistant.components.recorder.statistics import (  # noqa: PLC0415
        statistics_during_period,
    )

    ids = {
        statistic_id(key)
        for key in (
            ENTITY_KEY_SOLAR_SURPLUS,
            ENTITY_KEY_GRID_POWER,
            ENTITY_KEY_DATA_QUALITY,
        )
    }
    try:
        result = await get_instance(hass).async_add_executor_job(
            statistics_during_period,
            hass,
            start,
            end,
            ids,
            "hour",
            None,
            {"mean", "max", "min"},
        )
    except Exception:
        _LOGGER.exception("Could not read the statistics for yesterday")
        return _Rows()

    return _Rows(by_id={key: list(value) for key, value in result.items()})


def _hours_recorded(rows: _Rows) -> int:
    """Geef over hoeveel uur van gisteren er iets is vastgelegd.

    **Een dag met gaten is geen dag**, en het verschil is niet te zien aan de
    getallen zelf: zes uur zonneoverschot leest hetzelfde of de recorder nu
    vierentwintig uur kende of zeven. Home Assistant kan uit hebben gestaan voor
    een update, een stroomstoring of — zoals op de testinstance — omdat de doos
    pas 's middags aanging.

    De ruimste van de drie reeksen telt: een sensor kan afzonderlijk niets te
    melden hebben gehad, en dat is een ander verhaal dan een uur waarin niets
    draaide.
    """
    return max(
        len(rows.by_id.get(statistic_id(key), []))
        for key in (
            ENTITY_KEY_SOLAR_SURPLUS,
            ENTITY_KEY_GRID_POWER,
            ENTITY_KEY_DATA_QUALITY,
        )
    )


def _surplus_hours(rows: _Rows, config: StoredConfiguration) -> int | None:
    """Tel de uren waarin er zonneoverschot was dat de woning kon gebruiken.

    Tegen dezelfde drempel die het advies gebruikt (`min_solar_surplus_w`), want
    een ander getal hier zou een tweede antwoord zijn op "is dit de moeite waard"
    (SPEC.md §60.2 over dezelfde vraag op twee plekken).

    **Een uurgemiddelde is grof en de zin zegt dat ook**: een uur met een half
    uur dubbel overschot en een half uur niets telt hier mee. Daarom "ongeveer"
    in het paneel, en daarom een geheel aantal uren en geen kommagetal — precisie
    suggereren die er niet is, is erger dan afronden.
    """
    means = rows.values(ENTITY_KEY_SOLAR_SURPLUS, "mean")
    if not means:
        return None
    threshold = config.home.min_solar_surplus_w
    return sum(1 for value in means if value >= threshold)


def _peak_load(
    rows: _Rows, config: StoredConfiguration
) -> tuple[float | None, float | None]:
    """Geef het hoogste netvermogen van de dag, en wat dat van het maximum was.

    Het maximum per uur, niet het gemiddelde: een piek van een kwartier is
    precies waar de hoofdzekering om gaat, en die verdwijnt in een gemiddelde.

    **Alleen afname telt.** Teruglevering is ook belasting van de zekering
    (§16), maar zij komt hier als een negatief getal binnen en "het hoogste
    netvermogen" over een dag met zon zou dan over de import gaan die er niet
    was. Twee richtingen in één getal persen maakt het onleesbaar; de export van
    gisteren verdient een eigen feit, en dat is een van de drie niet.
    """
    maxima = rows.values(ENTITY_KEY_GRID_POWER, "max")
    if not maxima:
        return None, None
    peak = max(maxima)
    if peak <= 0:
        return None, None

    maximum = config.home.max_grid_power_w
    if not maximum:
        return round(peak, 1), None
    return round(peak, 1), round(peak / maximum * PERCENT_MAX, 1)


def _complete_all_day(rows: _Rows) -> bool | None:
    """Geef of de datakwaliteit de hele dag op honderd stond.

    Het minimum van de dag beantwoordt dat in één getal: één uur met een
    weggevallen bron drukt het omlaag en dan is het antwoord nee. Dat is
    bruikbaar bij een storingsmelding — "het werkte gisteren de hele dag" is
    iets anders dan "het werkte toen ik keek".
    """
    minima = rows.values(ENTITY_KEY_DATA_QUALITY, "min")
    if not minima:
        return None
    return min(minima) >= PERCENT_MAX
