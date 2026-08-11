"""Gisteren in drie feiten (SPEC.md §61).

Het gevoeligste aan deze module is niet wat zij uitrekent maar wat zij weigert:
een dagelijkse zelfbenutting uit uurgemiddelden. Dat getal oogt plausibel en
klopt in elke test, en het is structureel te hoog voor een woning met zon in de
ochtend — het gemiddelde van een verhouding is niet de verhouding van de sommen.
Er is dus een test die vastlegt dat het er niet in zit.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from custom_components.domotiapp_energy.const import (
    ENTITY_KEY_DATA_QUALITY,
    ENTITY_KEY_GRID_POWER,
    ENTITY_KEY_SOLAR_SURPLUS,
)
from custom_components.domotiapp_energy.engine.history import (
    DayHistory,
    _complete_all_day,
    _peak_load,
    _Rows,
    _surplus_hours,
    statistic_id,
    yesterday_bounds,
)
from custom_components.domotiapp_energy.models import HomeProfile, StoredConfiguration

TIME_ZONE = "Europe/Amsterdam"


def _config(**overrides: Any) -> StoredConfiguration:
    """Een woning met een drempel van 500 W en 5750 W maximum."""
    defaults: dict[str, Any] = {
        "main_fuse_a": 25,
        "max_grid_power_w": 5750.0,
        "min_solar_surplus_w": 500.0,
    }
    return StoredConfiguration(home=HomeProfile(**(defaults | overrides)))


def _rows(**per_key: list[dict[str, Any]]) -> _Rows:
    """Bouw uurrijen zoals de recorder ze teruggeeft, per entity-key."""
    return _Rows(by_id={statistic_id(key): value for key, value in per_key.items()})


def test_the_statistic_id_is_the_english_entity_id() -> None:
    """Waarom hier een geschiedenis op gebouwd kan worden (CLAUDE.md regel 11).

    Een Nederlandse installatie draagt dezelfde id als een Engelse. Zou de
    object-id de taal volgen, dan zou dit overzicht bij de helft van de klanten
    naar een reeks zoeken die niet bestaat.
    """
    assert (
        statistic_id(ENTITY_KEY_SOLAR_SURPLUS)
        == "sensor.domotiapp_energy_solar_surplus"
    )
    assert (
        statistic_id(ENTITY_KEY_DATA_QUALITY) == "sensor.domotiapp_energy_data_quality"
    )


async def test_yesterday_runs_from_midnight_to_midnight_locally(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Gisteren is een uitspraak van de bewoner, niet van de serverklok."""
    await hass.config.async_set_time_zone(TIME_ZONE)
    # 11 augustus 2026, 00:30 lokaal — dus nog geen half uur oud vandaag.
    now = datetime(2026, 8, 10, 22, 30, tzinfo=ZoneInfo("UTC"))

    start, end = yesterday_bounds(now)

    lokaal = ZoneInfo(TIME_ZONE)
    assert start.astimezone(lokaal).isoformat() == "2026-08-10T00:00:00+02:00"
    assert end.astimezone(lokaal).isoformat() == "2026-08-11T00:00:00+02:00"


async def test_surplus_hours_count_against_the_same_threshold_as_the_advice(
    hass: HomeAssistant,
) -> None:
    """Een ander getal hier zou een tweede antwoord zijn op dezelfde vraag."""
    rows = _rows(
        **{
            ENTITY_KEY_SOLAR_SURPLUS: [
                {"mean": 0.0},
                {"mean": 499.0},
                {"mean": 500.0},
                {"mean": 3200.0},
                {"mean": None},
            ]
        }
    )

    assert _surplus_hours(rows, _config()) == 2


async def test_no_statistics_means_no_number_rather_than_zero(
    hass: HomeAssistant,
) -> None:
    """Nul uur overschot is een bewering; niets weten is er geen."""
    assert _surplus_hours(_rows(), _config()) is None


async def test_the_peak_is_the_highest_hour_not_the_average(
    hass: HomeAssistant,
) -> None:
    """Een piek van een kwartier is waar de hoofdzekering om gaat.

    In een uurgemiddelde verdwijnt zij; in het uurmaximum niet.
    """
    rows = _rows(**{ENTITY_KEY_GRID_POWER: [{"max": 800.0}, {"max": 4600.0}]})

    watts, percent = _peak_load(rows, _config())

    assert watts == 4600.0
    assert percent == 80.0


async def test_a_day_of_only_export_reports_no_peak(hass: HomeAssistant) -> None:
    """Teruglevering komt hier negatief binnen en is een ander verhaal.

    Twee richtingen in één getal persen maakt het onleesbaar, dus een dag waarop
    de woning alleen terugleverde meldt geen hoogste netvermogen (§16).
    """
    rows = _rows(**{ENTITY_KEY_GRID_POWER: [{"max": -200.0}, {"max": -3000.0}]})

    assert _peak_load(rows, _config()) == (None, None)


async def test_complete_all_day_asks_the_minimum(hass: HomeAssistant) -> None:
    """Eén uur met een weggevallen bron maakt het antwoord nee.

    "Het werkte gisteren de hele dag" is iets anders dan "het werkte toen ik
    keek", en dat verschil is wat een storingsmelding bruikbaar maakt.
    """
    heel = _rows(**{ENTITY_KEY_DATA_QUALITY: [{"min": 100.0}]})
    assert _complete_all_day(heel) is True
    assert (
        _complete_all_day(
            _rows(**{ENTITY_KEY_DATA_QUALITY: [{"min": 100.0}, {"min": 80.0}]})
        )
        is False
    )
    assert _complete_all_day(_rows()) is None


async def test_the_day_never_carries_a_daily_self_consumption(
    hass: HomeAssistant,
) -> None:
    """**De belangrijkste test van dit bestand** (SPEC.md §61.3).

    Het gemiddelde van een verhouding is niet de verhouding van de sommen: een
    ochtenduur met 200 W opwek waarvan je alles gebruikt telt even zwaar als een
    middaguur met 4 kW waarvan je de helft terugleverde. Zo'n dagwaarde valt
    structureel te hoog uit voor precies de woning die het meest te winnen heeft,
    en zij klopt in elke test die haar eigen gemiddelde narekent.

    Deze test bewaakt de afwezigheid, want dat is het enige wat een test hier
    kan: zodra iemand het veld toevoegt, moet hij deze redenering tegenkomen.
    """
    velden = set(DayHistory(date="2026-08-10").to_dict())

    assert not [naam for naam in velden if "self_consumption" in naam]
    assert not [naam for naam in velden if "average" in naam or "gemiddeld" in naam]
