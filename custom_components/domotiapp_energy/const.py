"""Constants for the DomotiApp Energy integration.

Every value that is referenced from more than one module lives here, so that no
magic strings end up in the calculation engine, the WebSocket API or the panel.
Values are taken directly from SPEC.md; section references are noted per block.
"""

from __future__ import annotations

from typing import Final

# --- Identity (SPEC.md §3) --------------------------------------------------

DOMAIN: Final = "domotiapp_energy"
INTEGRATION_NAME: Final = "DomotiApp Energy"
VERSION: Final = "0.1.0"

MANUFACTURER: Final = "DomotiApp"
DEVICE_MODEL: Final = "Energy Coach"

# --- Config entry (SPEC.md §6) ----------------------------------------------

CONF_HOME_NAME: Final = "home_name"
CONF_MANUAL_SETUP_ACKNOWLEDGED: Final = "manual_setup_acknowledged"

DEFAULT_HOME_NAME: Final = "Mijn woning"

# --- Side panel (SPEC.md §7) ------------------------------------------------

PANEL_URL_PATH: Final = "domotiapp-energy"
PANEL_TITLE: Final = "DomotiApp Energy"
PANEL_ICON: Final = "mdi:home-lightning-bolt"
PANEL_COMPONENT_NAME: Final = "domotiapp-energy-panel"

FRONTEND_URL_BASE: Final = "/domotiapp_energy_frontend"
FRONTEND_DIR_NAME: Final = "frontend"
# The ?v= query string is mandatory against aggressive frontend caching and is
# tied to VERSION so that every release busts the browser cache.
PANEL_MODULE_URL: Final = f"{FRONTEND_URL_BASE}/{PANEL_COMPONENT_NAME}.js?v={VERSION}"

# --- Storage (SPEC.md §13) --------------------------------------------------

STORAGE_KEY: Final = f"{DOMAIN}.config"
STORAGE_VERSION: Final = 1
STORAGE_MINOR_VERSION: Final = 1
SCHEMA_VERSION: Final = 1

MAX_LOG_ENTRIES: Final = 200
# Identical consecutive events within this window bump a counter instead of
# adding a new log line (anti-spam rule, SPEC.md §8 "Logboek").
LOG_DEDUPE_WINDOW_MINUTES: Final = 15

# Revision of a configuration that has never been written.
INITIAL_REVISION: Final = 1

# --- WebSocket API (SPEC.md §14) --------------------------------------------

WS_CONFIG_GET: Final = f"{DOMAIN}/config/get"
WS_HOME_UPDATE: Final = f"{DOMAIN}/home/update"
WS_SOURCES_LIST: Final = f"{DOMAIN}/sources/list"
WS_SOURCES_CREATE: Final = f"{DOMAIN}/sources/create"
WS_SOURCES_UPDATE: Final = f"{DOMAIN}/sources/update"
WS_SOURCES_DELETE: Final = f"{DOMAIN}/sources/delete"
WS_DEVICES_LIST: Final = f"{DOMAIN}/devices/list"
WS_DEVICES_CREATE: Final = f"{DOMAIN}/devices/create"
WS_DEVICES_UPDATE: Final = f"{DOMAIN}/devices/update"
WS_DEVICES_DELETE: Final = f"{DOMAIN}/devices/delete"
WS_PREFERENCES_GET: Final = f"{DOMAIN}/preferences/get"
WS_PREFERENCES_UPDATE: Final = f"{DOMAIN}/preferences/update"
WS_COACH_GET: Final = f"{DOMAIN}/coach/get"
WS_COACH_RECALCULATE: Final = f"{DOMAIN}/coach/recalculate"
WS_LOGS_LIST: Final = f"{DOMAIN}/logs/list"
WS_LOGS_CLEAR: Final = f"{DOMAIN}/logs/clear"

ATTR_EXPECTED_REVISION: Final = "expected_revision"
ATTR_REVISION: Final = "revision"
ATTR_ITEM: Final = "item"

# Marks a stored source or device that the engine must never use. A row whose
# type is unrecognised keeps that type verbatim: substituting a known type
# would feed the calculations a guess, which SPEC.md §2.1 forbids.
INVALID_REASON_UNKNOWN_TYPE: Final = "unknown_type"

ERR_NOT_FOUND: Final = "not_found"
ERR_DUPLICATE_ID: Final = "duplicate_id"
ERR_INVALID_FORMAT: Final = "invalid_format"
ERR_REVISION_CONFLICT: Final = "revision_conflict"
ERR_NOT_AUTHORIZED: Final = "not_authorized"
ERR_STORAGE_ERROR: Final = "storage_error"

# --- Services (SPEC.md §20) -------------------------------------------------

SERVICE_RECALCULATE: Final = "recalculate"
SERVICE_CLEAR_LOG: Final = "clear_log"

# --- Home profile (SPEC.md §8 "Woning") -------------------------------------

PHASES_SINGLE: Final = 1
PHASES_THREE: Final = 3
ALLOWED_PHASES: Final[tuple[int, ...]] = (PHASES_SINGLE, PHASES_THREE)
# A single-phase connection is the conservative assumption: it yields the
# lowest theoretical maximum, so nothing is ever over-estimated by default.
DEFAULT_PHASES: Final = PHASES_SINGLE

# Nominal grid voltage per phase, used only for the informational hint
# "theoretical maximum = phases x 230 V x main_fuse_a". Calculations use
# max_grid_power_w exclusively.
NOMINAL_VOLTAGE_PER_PHASE: Final = 230

MIN_MAIN_FUSE_A: Final = 1
MAX_MAIN_FUSE_A: Final = 100

CONTRACT_TYPE_FIXED: Final = "fixed"
CONTRACT_TYPE_DYNAMIC: Final = "dynamic"
CONTRACT_TYPES: Final[tuple[str, ...]] = (CONTRACT_TYPE_FIXED, CONTRACT_TYPE_DYNAMIC)
# A fixed contract never produces price advice, so it is the safe default:
# no advice is generated until the installer explicitly selects "dynamic".
DEFAULT_CONTRACT_TYPE: Final = CONTRACT_TYPE_FIXED

STRATEGY_COMFORT: Final = "comfort"
STRATEGY_BALANCED: Final = "balanced"
STRATEGY_SAVE: Final = "save"
STRATEGY_MAX_SELF_CONSUMPTION: Final = "max_self_consumption"
STRATEGIES: Final[tuple[str, ...]] = (
    STRATEGY_COMFORT,
    STRATEGY_BALANCED,
    STRATEGY_SAVE,
    STRATEGY_MAX_SELF_CONSUMPTION,
)

DEFAULT_PEAK_WARNING_PERCENT: Final = 80
DEFAULT_MIN_SOLAR_SURPLUS_W: Final = 500
DEFAULT_STRATEGY: Final = STRATEGY_BALANCED

# --- Control levels (SPEC.md §2.2 and §8 "Apparaten") -----------------------

CONTROL_MONITOR_ONLY: Final = "monitor_only"
CONTROL_ADVICE_ONLY: Final = "advice_only"
CONTROL_APPROVAL_REQUIRED: Final = "approval_required"
CONTROL_AUTOMATIC: Final = "automatic"
CONTROL_MODES: Final[tuple[str, ...]] = (
    CONTROL_MONITOR_ONLY,
    CONTROL_ADVICE_ONLY,
    CONTROL_APPROVAL_REQUIRED,
    CONTROL_AUTOMATIC,
)
# In 0.1.0 everything except monitor_only is forced to advice_only.
DEFAULT_CONTROL_MODE: Final = CONTROL_ADVICE_ONLY
CONTROL_LEVEL_0_1_0: Final = CONTROL_ADVICE_ONLY

# --- Energy sources (SPEC.md §8 "Energiebronnen") ---------------------------

SOURCE_TYPE_GRID_METER: Final = "grid_meter"
SOURCE_TYPE_SOLAR: Final = "solar"
SOURCE_TYPE_CURRENT_PRICE: Final = "current_price"
SOURCE_TYPE_PRICE_FORECAST: Final = "price_forecast"
SOURCE_TYPE_SOLAR_FORECAST: Final = "solar_forecast"
SOURCE_TYPE_HOME_BATTERY: Final = "home_battery"
SOURCE_TYPE_GENERAL_CONSUMPTION: Final = "general_consumption"
SOURCE_TYPES: Final[tuple[str, ...]] = (
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_SOLAR,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_PRICE_FORECAST,
    SOURCE_TYPE_SOLAR_FORECAST,
    SOURCE_TYPE_HOME_BATTERY,
    SOURCE_TYPE_GENERAL_CONSUMPTION,
)

VALUE_SOURCE_STATE: Final = "state"
VALUE_SOURCE_ATTRIBUTE: Final = "attribute"
VALUE_SOURCES: Final[tuple[str, ...]] = (VALUE_SOURCE_STATE, VALUE_SOURCE_ATTRIBUTE)

# Explicit unit enum. Conversion is based on this choice plus scale_factor only,
# never on the Home Assistant unit_of_measurement or the entity name.
UNIT_W: Final = "W"
UNIT_KW: Final = "kW"
UNIT_A: Final = "A"
UNIT_WH: Final = "Wh"
UNIT_KWH: Final = "kWh"
UNIT_EUR_KWH: Final = "EUR/kWh"
UNIT_CT_KWH: Final = "ct/kWh"
UNIT_PERCENT: Final = "%"
UNIT_NONE: Final = "none"
UNITS: Final[tuple[str, ...]] = (
    UNIT_W,
    UNIT_KW,
    UNIT_A,
    UNIT_WH,
    UNIT_KWH,
    UNIT_EUR_KWH,
    UNIT_CT_KWH,
    UNIT_PERCENT,
    UNIT_NONE,
)

DEFAULT_SCALE_FACTOR: Final = 1.0

METER_MODE_SINGLE_SIGNED: Final = "single_signed"
METER_MODE_SEPARATE: Final = "separate_import_export"
METER_MODES: Final[tuple[str, ...]] = (
    METER_MODE_SINGLE_SIGNED,
    METER_MODE_SEPARATE,
)

POSITIVE_MEANS_IMPORT: Final = "import"
POSITIVE_MEANS_EXPORT: Final = "export"
POSITIVE_MEANS_OPTIONS: Final[tuple[str, ...]] = (
    POSITIVE_MEANS_IMPORT,
    POSITIVE_MEANS_EXPORT,
)

# --- Device profiles (SPEC.md §8 "Apparaten") -------------------------------

DEVICE_TYPE_EV_CHARGER: Final = "ev_charger"
DEVICE_TYPE_HOME_BATTERY: Final = "home_battery"
DEVICE_TYPE_HEAT_PUMP: Final = "heat_pump"
DEVICE_TYPE_ELECTRIC_BOILER: Final = "electric_boiler"
DEVICE_TYPE_DISHWASHER: Final = "dishwasher"
DEVICE_TYPE_WASHING_MACHINE: Final = "washing_machine"
DEVICE_TYPE_DRYER: Final = "dryer"
DEVICE_TYPE_AIR_CONDITIONING: Final = "air_conditioning"
DEVICE_TYPE_POOL_PUMP: Final = "pool_pump"
DEVICE_TYPE_GENERIC_SCHEDULABLE: Final = "generic_schedulable"
DEVICE_TYPE_GENERIC_MONITOR: Final = "generic_monitor"
DEVICE_TYPES: Final[tuple[str, ...]] = (
    DEVICE_TYPE_EV_CHARGER,
    DEVICE_TYPE_HOME_BATTERY,
    DEVICE_TYPE_HEAT_PUMP,
    DEVICE_TYPE_ELECTRIC_BOILER,
    DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_WASHING_MACHINE,
    DEVICE_TYPE_DRYER,
    DEVICE_TYPE_AIR_CONDITIONING,
    DEVICE_TYPE_POOL_PUMP,
    DEVICE_TYPE_GENERIC_SCHEDULABLE,
    DEVICE_TYPE_GENERIC_MONITOR,
)

# Device types that default to is_noisy = true (SPEC.md §8).
NOISY_BY_DEFAULT_DEVICE_TYPES: Final[frozenset[str]] = frozenset(
    {
        DEVICE_TYPE_WASHING_MACHINE,
        DEVICE_TYPE_DRYER,
        DEVICE_TYPE_DISHWASHER,
        DEVICE_TYPE_POOL_PUMP,
    }
)

# Device types that default to is_flexible = false (SPEC.md §8).
INFLEXIBLE_BY_DEFAULT_DEVICE_TYPES: Final[frozenset[str]] = frozenset(
    {
        DEVICE_TYPE_GENERIC_MONITOR,
        DEVICE_TYPE_HEAT_PUMP,
    }
)

PRIORITY_LOW: Final = "low"
PRIORITY_NORMAL: Final = "normal"
PRIORITY_HIGH: Final = "high"
PRIORITY_CRITICAL: Final = "critical"
PRIORITIES: Final[tuple[str, ...]] = (
    PRIORITY_LOW,
    PRIORITY_NORMAL,
    PRIORITY_HIGH,
    PRIORITY_CRITICAL,
)
DEFAULT_PRIORITY: Final = PRIORITY_NORMAL

# Optional entity bindings on a device profile. Missing means null or absent,
# never an empty string.
DEVICE_ENTITY_BINDING_KEYS: Final[tuple[str, ...]] = (
    "status_entity",
    "power_entity",
    "energy_entity",
    "remaining_time_entity",
    "temperature_entity",
    "battery_level_entity",
)

# --- Preferences (SPEC.md §8 "Voorkeuren") ----------------------------------

# Weekday numbering follows datetime.weekday(): Monday = 0 ... Sunday = 6, so
# a stored day list can be compared directly against dt_util.now().weekday().
ALL_DAYS_OF_WEEK: Final[tuple[int, ...]] = (0, 1, 2, 3, 4, 5, 6)
MIN_DAY_OF_WEEK: Final = 0
MAX_DAY_OF_WEEK: Final = 6

DEFAULT_QUIET_HOURS_START: Final = "22:00"
DEFAULT_QUIET_HOURS_END: Final = "07:00"
DEFAULT_MIN_SAVINGS_EUR: Final = 0.0
DEFAULT_MAX_ADVICE_COUNT: Final = 3
MIN_ADVICE_COUNT: Final = 1
MAX_ADVICE_COUNT: Final = 5

# --- Logbook (SPEC.md §8 "Logboek") -----------------------------------------

LOG_EVENT_CONFIG_CHANGED: Final = "config_changed"
LOG_EVENT_DEVICE_ADDED: Final = "device_added"
LOG_EVENT_DEVICE_REMOVED: Final = "device_removed"
LOG_EVENT_ADVICE_RECALCULATED: Final = "advice_recalculated"
LOG_EVENT_SOURCE_UNAVAILABLE: Final = "source_unavailable"
LOG_EVENT_INVALID_MEASUREMENT: Final = "invalid_measurement"
LOG_EVENT_PEAK_RISK_DETECTED: Final = "peak_risk_detected"
LOG_EVENT_SOLAR_SURPLUS_DETECTED: Final = "solar_surplus_detected"
# Added on top of the eight types in SPEC.md §8: a stored row with an
# unrecognised type is a configuration problem, not an availability problem
# (source_unavailable) and not a bad reading (invalid_measurement).
LOG_EVENT_INVALID_CONFIGURATION: Final = "invalid_configuration"
LOG_EVENT_TYPES: Final[tuple[str, ...]] = (
    LOG_EVENT_CONFIG_CHANGED,
    LOG_EVENT_DEVICE_ADDED,
    LOG_EVENT_DEVICE_REMOVED,
    LOG_EVENT_ADVICE_RECALCULATED,
    LOG_EVENT_SOURCE_UNAVAILABLE,
    LOG_EVENT_INVALID_MEASUREMENT,
    LOG_EVENT_PEAK_RISK_DETECTED,
    LOG_EVENT_SOLAR_SURPLUS_DETECTED,
    LOG_EVENT_INVALID_CONFIGURATION,
)

SEVERITY_INFO: Final = "info"
SEVERITY_WARNING: Final = "warning"
SEVERITY_ERROR: Final = "error"
SEVERITY_SUCCESS: Final = "success"
SEVERITIES: Final[tuple[str, ...]] = (
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SEVERITY_ERROR,
    SEVERITY_SUCCESS,
)

# --- Confidence (SPEC.md §16) -----------------------------------------------

CONFIDENCE_LOW: Final = "low"
CONFIDENCE_MEDIUM: Final = "medium"
CONFIDENCE_HIGH: Final = "high"
CONFIDENCE_LEVELS: Final[tuple[str, ...]] = (
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_HIGH,
)

# --- Data quality checklist (SPEC.md §16 "Datakwaliteit") -------------------

COMPLETENESS_ITEM_HOME: Final = "home_profile_complete"
COMPLETENESS_ITEM_GRID: Final = "grid_source_valid"
COMPLETENESS_ITEM_SOLAR: Final = "solar_source_valid"
COMPLETENESS_ITEM_PRICE: Final = "price_information_available"
COMPLETENESS_ITEM_DEVICE_PROFILE: Final = "device_profile_complete"
COMPLETENESS_ITEM_TIME_WINDOWS: Final = "flexible_devices_have_time_window"

COMPLETENESS_POINTS: Final[dict[str, int]] = {
    COMPLETENESS_ITEM_HOME: 20,
    COMPLETENESS_ITEM_GRID: 25,
    COMPLETENESS_ITEM_SOLAR: 15,
    COMPLETENESS_ITEM_PRICE: 15,
    COMPLETENESS_ITEM_DEVICE_PROFILE: 15,
    COMPLETENESS_ITEM_TIME_WINDOWS: 10,
}

# --- Energy score weights (SPEC.md §16 "Energiescore") ----------------------

SCORE_WEIGHT_DATA_QUALITY: Final = 0.30
SCORE_WEIGHT_PEAK: Final = 0.25
SCORE_WEIGHT_SOLAR: Final = 0.20
SCORE_WEIGHT_PRICE: Final = 0.15
SCORE_WEIGHT_FLEXIBILITY: Final = 0.10

# Peak component is 100 below this load percentage and drops linearly to 0 at 100%.
PEAK_COMPONENT_FULL_BELOW_PERCENT: Final = 50.0
# A fixed contract has no price signal, so the price component is neutral.
PRICE_COMPONENT_FIXED_CONTRACT: Final = 50.0

SCORE_MIN: Final = 0
SCORE_MAX: Final = 100

# --- Coordinator (SPEC.md §18) ----------------------------------------------

RECALCULATE_DEBOUNCE_SECONDS: Final = 2.0
SAFETY_RECALCULATE_INTERVAL_MINUTES: Final = 5

# --- Entities (SPEC.md §19) -------------------------------------------------

ENTITY_KEY_ENERGY_SCORE: Final = "score"
ENTITY_KEY_DATA_QUALITY: Final = "data_quality"
ENTITY_KEY_GRID_POWER: Final = "grid_power"
ENTITY_KEY_SOLAR_SURPLUS: Final = "solar_surplus"
ENTITY_KEY_CURRENT_ADVICE: Final = "current_advice"
ENTITY_KEY_PEAK_RISK: Final = "peak_risk"

# Exact object IDs, forced via _attr_suggested_object_id so that the entity IDs
# documented in the README are stable.
SUGGESTED_OBJECT_IDS: Final[dict[str, str]] = {
    ENTITY_KEY_ENERGY_SCORE: "domotiapp_energy_score",
    ENTITY_KEY_DATA_QUALITY: "domotiapp_energy_data_quality",
    ENTITY_KEY_GRID_POWER: "domotiapp_energy_grid_power",
    ENTITY_KEY_SOLAR_SURPLUS: "domotiapp_energy_solar_surplus",
    ENTITY_KEY_CURRENT_ADVICE: "domotiapp_energy_current_advice",
    ENTITY_KEY_PEAK_RISK: "domotiapp_energy_peak_risk",
}

# Home Assistant rejects a state longer than 255 characters.
MAX_STATE_LENGTH: Final = 255
# Keep the advice attributes well under the recorder/state-machine budget.
MAX_ADVICE_ITEMS_IN_ATTRIBUTES: Final = 5

# --- Coach question selector (SPEC.md §8 "Energiecoach") --------------------

EXPLANATION_KEY_WHY_ADVICE: Final = "why_advice"
EXPLANATION_KEY_USE_DEVICE_NOW: Final = "use_device_now"
EXPLANATION_KEY_PEAK_RISK: Final = "peak_risk"
EXPLANATION_KEY_MISSING_DATA: Final = "missing_data"
EXPLANATION_KEY_SCORE_BREAKDOWN: Final = "score_breakdown"
EXPLANATION_KEYS: Final[tuple[str, ...]] = (
    EXPLANATION_KEY_WHY_ADVICE,
    EXPLANATION_KEY_USE_DEVICE_NOW,
    EXPLANATION_KEY_PEAK_RISK,
    EXPLANATION_KEY_MISSING_DATA,
    EXPLANATION_KEY_SCORE_BREAKDOWN,
)
