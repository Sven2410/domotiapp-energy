"""Tests for the Home Assistant entities (SPEC.md §19 and §24).

The entity-id tests are the important ones: SPEC.md §19 fixes six ids that go
into the README and that customers build dashboards and automations on. Three
things can move them, and there is a test for each:

* the customer's language, because Home Assistant derives the object id from
  the native entity name for the 41 languages in ``NATIVE_ENTITY_IDS``
  (including Dutch) — the reason ``suggested_object_id`` is pinned at all;
* a rename in ``translations/en.json`` that is not mirrored in
  ``ENTITY_OBJECT_ID_NAMES``;
* the device name, which Home Assistant prefixes onto the id, and which is
  therefore fixed to ``DomotiApp Energy`` instead of the home name.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import domotiapp_energy
from custom_components.domotiapp_energy.const import (
    ATTR_ADVICE_CONFIDENCE,
    ATTR_ADVICE_ITEMS,
    ATTR_ADVICE_MESSAGE,
    ATTR_ADVICE_REASON_CODE,
    CONF_HOME_NAME,
    CONF_MANUAL_SETUP_ACKNOWLEDGED,
    CONFIDENCE_HIGH,
    DEFAULT_HOME_NAME,
    DEVICE_MODEL,
    DEVICE_TYPE_DISHWASHER,
    DOMAIN,
    ENTITY_KEY_CURRENT_ADVICE,
    ENTITY_KEY_DATA_QUALITY,
    ENTITY_KEY_ENERGY_SCORE,
    ENTITY_KEY_GRID_POWER,
    ENTITY_KEY_PEAK_RISK,
    ENTITY_KEY_SOLAR_SURPLUS,
    ENTITY_OBJECT_ID_NAMES,
    INTEGRATION_NAME,
    MANUFACTURER,
    MAX_ADVICE_ITEMS_IN_ATTRIBUTES,
    MAX_STATE_LENGTH,
    METER_MODE_SINGLE_SIGNED,
    POSITIVE_MEANS_IMPORT,
    SEVERITY_INFO,
    SOURCE_TYPE_GRID_METER,
    STORAGE_KEY,
    STORAGE_VERSION,
    UNIT_W,
    VERSION,
)
from custom_components.domotiapp_energy.models import (
    AdviceItem,
    CoachResult,
    DeviceProfile,
    EnergySource,
    HomeProfile,
    StoredConfiguration,
)

GRID_ENTITY = "sensor.netmeter"

# The six ids SPEC.md §19 fixes. Written out in full rather than built from a
# constant: the point of the test is that the derivation produces exactly these.
SENSOR_SCORE = "sensor.domotiapp_energy_score"
SENSOR_DATA_QUALITY = "sensor.domotiapp_energy_data_quality"
SENSOR_GRID_POWER = "sensor.domotiapp_energy_grid_power"
SENSOR_SOLAR_SURPLUS = "sensor.domotiapp_energy_solar_surplus"
SENSOR_CURRENT_ADVICE = "sensor.domotiapp_energy_current_advice"
BINARY_SENSOR_PEAK_RISK = "binary_sensor.domotiapp_energy_peak_risk"


def _stored_configuration() -> dict[str, Any]:
    """Return a configuration with a usable grid meter and one appliance."""
    config = StoredConfiguration(
        home=HomeProfile(
            home_name=DEFAULT_HOME_NAME,
            main_fuse_a=25,
            max_grid_power_w=5750.0,
            fixed_import_price_eur_kwh=0.30,
            feed_in_price_eur_kwh=0.08,
        ),
        sources=[
            EnergySource.from_dict(
                {
                    "id": "grid",
                    "name": "Netmeter",
                    "type": SOURCE_TYPE_GRID_METER,
                    "entity_id": GRID_ENTITY,
                    "unit": UNIT_W,
                    "meter_mode": METER_MODE_SINGLE_SIGNED,
                    "positive_means": POSITIVE_MEANS_IMPORT,
                }
            )
        ],
        devices=[
            DeviceProfile.from_dict(
                {
                    "id": "dishwasher",
                    "name": "Vaatwasser",
                    "device_type": DEVICE_TYPE_DISHWASHER,
                    "nominal_power_w": 2000.0,
                    "energy_per_cycle_kwh": 1.0,
                    "ready_from": "00:00",
                    "ready_before": "23:59",
                }
            )
        ],
    )
    return config.to_dict()


@pytest.fixture(name="entry")
async def entry_fixture(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> MockConfigEntry:
    """Set up the integration with a configured grid meter reading 1000 W."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": _stored_configuration(),
    }
    hass.states.async_set(GRID_ENTITY, "1000")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_HOME_NAME,
        data={
            CONF_HOME_NAME: DEFAULT_HOME_NAME,
            CONF_MANUAL_SETUP_ACKNOWLEDGED: True,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_the_six_entity_ids_are_built_from_the_pinned_english_names(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The six ids of SPEC.md §19 exist, and the registry shows how.

    ``object_id_base`` is the name Home Assistant prefixed with the device name
    to reach the id. It has to be the pinned English name: that is what stops a
    Dutch installation from getting ``sensor.domotiapp_energy_energiescore``.
    ``suggested_object_id`` stays ``None``, which proves the device-name prefix
    still comes from Home Assistant instead of being hard-coded here.
    """
    registry = er.async_get(hass)

    expected = {
        SENSOR_SCORE: ENTITY_KEY_ENERGY_SCORE,
        SENSOR_DATA_QUALITY: ENTITY_KEY_DATA_QUALITY,
        SENSOR_GRID_POWER: ENTITY_KEY_GRID_POWER,
        SENSOR_SOLAR_SURPLUS: ENTITY_KEY_SOLAR_SURPLUS,
        SENSOR_CURRENT_ADVICE: ENTITY_KEY_CURRENT_ADVICE,
        BINARY_SENSOR_PEAK_RISK: ENTITY_KEY_PEAK_RISK,
    }

    for entity_id, key in expected.items():
        registry_entry = registry.async_get(entity_id)
        assert registry_entry is not None, f"{entity_id} was not created"
        assert registry_entry.unique_id == f"{entry.entry_id}_{key}"
        assert registry_entry.translation_key == key
        assert registry_entry.has_entity_name is True
        assert registry_entry.object_id_base == ENTITY_OBJECT_ID_NAMES[key]
        assert registry_entry.suggested_object_id is None


async def test_the_pinned_names_match_the_english_translations(
    hass: HomeAssistant,
) -> None:
    """The pinned names and translations/en.json must not drift apart.

    The English names exist twice on purpose: reading the translation file at
    runtime would be blocking I/O in the event loop. This test is what keeps
    the copy honest, so renaming an entity in en.json without touching
    ENTITY_OBJECT_ID_NAMES fails here instead of silently moving the entity ids
    of every new installation.
    """
    translations_file = (
        Path(domotiapp_energy.__file__).parent / "translations" / "en.json"
    )
    translations = json.loads(translations_file.read_text(encoding="utf-8"))["entity"]

    names = {
        key: entry["name"]
        for platform in translations.values()
        for key, entry in platform.items()
    }

    assert names == ENTITY_OBJECT_ID_NAMES


@pytest.mark.parametrize("language", ["en", "nl"])
async def test_entity_ids_do_not_follow_the_user_language(
    hass: HomeAssistant, hass_storage: dict[str, Any], language: str
) -> None:
    """The six ids are the same whatever language the customer runs.

    Home Assistant derives the object id from the *native* entity name for
    every language in ``homeassistant.generated.languages.NATIVE_ENTITY_IDS``,
    and Dutch is in that set. Without a guard, a Dutch installation gets
    ``sensor.domotiapp_energy_energiescore`` and an English one
    ``sensor.domotiapp_energy_score`` — the exact drift SPEC.md §19 forbids.
    """
    await hass.config.async_update(language=language)

    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": _stored_configuration(),
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_HOME_NAME,
        data={
            CONF_HOME_NAME: DEFAULT_HOME_NAME,
            CONF_MANUAL_SETUP_ACKNOWLEDGED: True,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in (
        SENSOR_SCORE,
        SENSOR_DATA_QUALITY,
        SENSOR_GRID_POWER,
        SENSOR_SOLAR_SURPLUS,
        SENSOR_CURRENT_ADVICE,
        BINARY_SENSOR_PEAK_RISK,
    ):
        assert hass.states.get(entity_id) is not None, (
            f"{entity_id} is missing with language {language!r}"
        )

    # The id is pinned, the visible name is not: a Dutch installation still
    # reads Dutch. Anyone "fixing" this by setting _attr_name would freeze the
    # displayed name in English, and this assertion stops that.
    expected_name = (
        "DomotiApp Energy Energiescore"
        if language == "nl"
        else ("DomotiApp Energy Score")
    )
    state = hass.states.get(SENSOR_SCORE)
    assert state is not None
    assert state.attributes["friendly_name"] == expected_name


async def test_the_device_is_named_after_the_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The device name is fixed, so the entity ids do not vary per customer.

    The home name is deliberately not used here: it feeds the object id, and a
    per-customer device name would give every installation different entity ids
    (SPEC.md §19).
    """
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})

    assert device is not None
    assert device.name == INTEGRATION_NAME
    assert device.manufacturer == MANUFACTURER
    assert device.model == DEVICE_MODEL
    assert device.sw_version == VERSION


async def test_a_different_home_name_does_not_move_the_entity_ids(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Another home name yields exactly the same six entity ids."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": _stored_configuration(),
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Woning Van Dijk",
        data={
            CONF_HOME_NAME: "Woning Van Dijk",
            CONF_MANUAL_SETUP_ACKNOWLEDGED: True,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(SENSOR_SCORE) is not None
    assert hass.states.get(BINARY_SENSOR_PEAK_RISK) is not None


async def test_sensor_states_and_units(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Every sensor carries the value and the unit SPEC.md §19 prescribes."""
    grid_power = hass.states.get(SENSOR_GRID_POWER)
    assert grid_power is not None
    assert float(grid_power.state) == 1000.0
    assert grid_power.attributes["unit_of_measurement"] == UnitOfPower.WATT
    assert grid_power.attributes["device_class"] == "power"

    # Importing 1000 W means there is no surplus, which is a measurement of
    # zero rather than an unknown.
    surplus = hass.states.get(SENSOR_SOLAR_SURPLUS)
    assert surplus is not None
    assert float(surplus.state) == 0.0

    data_quality = hass.states.get(SENSOR_DATA_QUALITY)
    assert data_quality is not None
    assert data_quality.attributes["unit_of_measurement"] == "%"
    # This home has no solar row, so the solar item is not asked of it and its
    # 15 points leave the divisor with them. Everything that *is* asked passes,
    # and that is what 100 means: complete for this home, not complete for a
    # home with panels. It used to read 85 with no way to ever reach more.
    assert int(data_quality.state) == 100

    score = hass.states.get(SENSOR_SCORE)
    assert score is not None
    assert 0 <= int(score.state) <= 100
    assert "unit_of_measurement" not in score.attributes

    peak_risk = hass.states.get(BINARY_SENSOR_PEAK_RISK)
    assert peak_risk is not None
    assert peak_risk.state == STATE_OFF
    assert peak_risk.attributes["device_class"] == "problem"


async def test_entities_stay_available_without_data(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Missing source data yields unknown, never unavailable (SPEC.md §19)."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": StoredConfiguration().to_dict(),
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOME_NAME: DEFAULT_HOME_NAME,
            CONF_MANUAL_SETUP_ACKNOWLEDGED: True,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in (SENSOR_GRID_POWER, SENSOR_SOLAR_SURPLUS, BINARY_SENSOR_PEAK_RISK):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN

    # The data quality meter is always computable, so it must show a number
    # exactly when everything else is unknown.
    data_quality = hass.states.get(SENSOR_DATA_QUALITY)
    assert data_quality is not None
    assert int(data_quality.state) == 0


async def test_entities_update_after_a_recalculation(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A new reading on a linked entity moves the sensors and the peak risk."""
    hass.states.async_set(GRID_ENTITY, "5000")
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    grid_power = hass.states.get(SENSOR_GRID_POWER)
    assert grid_power is not None
    assert float(grid_power.state) == 5000.0

    # 5000 of 5750 W is 87%, above the default warning level of 80%.
    peak_risk = hass.states.get(BINARY_SENSOR_PEAK_RISK)
    assert peak_risk is not None
    assert peak_risk.state == STATE_ON
    assert peak_risk.attributes["grid_load_percent"] == pytest.approx(87.0, abs=0.1)


async def test_advice_sensor_carries_the_full_text_in_attributes(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The state is the title; message, reason and confidence are attributes."""
    state = hass.states.get(SENSOR_CURRENT_ADVICE)

    assert state is not None
    assert state.state
    assert state.attributes[ATTR_ADVICE_MESSAGE]
    assert state.attributes[ATTR_ADVICE_REASON_CODE]
    assert state.attributes[ATTR_ADVICE_CONFIDENCE]
    assert len(state.attributes[ATTR_ADVICE_ITEMS]) <= MAX_ADVICE_ITEMS_IN_ATTRIBUTES


async def test_advice_state_is_truncated_to_255_characters(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A long title is cut to the maximum a Home Assistant state may hold.

    Home Assistant refuses a longer state outright, so truncating is what keeps
    the sensor alive at all (SPEC.md §19).
    """
    long_title = "Zeer uitgebreide adviestitel " * 20
    assert len(long_title) > MAX_STATE_LENGTH

    coordinator = entry.runtime_data.coordinator
    result = coordinator.data
    result.primary_advice = AdviceItem(
        id="long",
        title=long_title,
        message="Volledige tekst blijft in de attributen staan.",
        severity=SEVERITY_INFO,
        reason_code="neutral_energy_situation",
        confidence=CONFIDENCE_HIGH,
    )
    coordinator.async_set_updated_data(result)
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_CURRENT_ADVICE)
    assert state is not None
    assert len(state.state) == MAX_STATE_LENGTH
    assert state.state == long_title[:MAX_STATE_LENGTH]
    assert state.attributes[ATTR_ADVICE_MESSAGE] == (
        "Volledige tekst blijft in de attributen staan."
    )


async def test_advice_sensor_is_unknown_without_advice(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """No primary advice leaves the state unknown rather than empty."""
    coordinator = entry.runtime_data.coordinator
    coordinator.async_set_updated_data(CoachResult())
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_CURRENT_ADVICE)
    assert state is not None
    assert state.state == STATE_UNKNOWN
