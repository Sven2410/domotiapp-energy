"""Constants for the DomotiApp Energy integration.

Every value that is referenced from more than one module lives here, so that no
magic strings end up in the calculation engine, the WebSocket API or the panel.
Values are taken directly from SPEC.md; section references are noted per block.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

# --- Identity (SPEC.md §3) --------------------------------------------------

DOMAIN: Final = "domotiapp_energy"
INTEGRATION_NAME: Final = "DomotiApp Energy"
VERSION: Final = "0.5.0"

MANUFACTURER: Final = "DomotiApp"
DEVICE_MODEL: Final = "Energy Coach"

# --- Config entry (SPEC.md §6) ----------------------------------------------

CONF_HOME_NAME: Final = "home_name"
CONF_MANUAL_SETUP_ACKNOWLEDGED: Final = "manual_setup_acknowledged"

DEFAULT_HOME_NAME: Final = "Mijn woning"

# Shown when the installer submits the form without confirming that the
# integration configures nothing by itself. The key is looked up under
# config.error in translations/*.json.
ERROR_ACKNOWLEDGEMENT_REQUIRED: Final = "acknowledgement_required"

# --- Side panel (SPEC.md §7) ------------------------------------------------

PANEL_URL_PATH: Final = "domotiapp-energy"
PANEL_TITLE: Final = "DomotiApp Energy"
PANEL_ICON: Final = "mdi:home-lightning-bolt"
PANEL_COMPONENT_NAME: Final = "domotiapp-energy-panel"

# The version is part of the *path*, not only of a query string, and that is the
# only thing that actually busts the cache for the whole panel.
#
# SPEC.md §7 requires ``?v=`` on the module URL, and it does bust the entry
# point. It cannot bust anything else: a relative ``import './core/dom.js'``
# does not inherit the query of the module it sits in, so every other file keeps
# its plain URL. Home Assistant's service worker caches those by exact URL, and
# in the test instance it served the previous release's tab modules to a browser
# that had just loaded the new entry point — a half-old, half-new panel, and a
# bug report nobody could reproduce.
#
# Putting the version in the base makes every URL under it change per release,
# without repeating the version in fifteen import statements that would have to
# be bumped by hand.
FRONTEND_URL_ROOT: Final = "/domotiapp_energy_frontend"
FRONTEND_URL_BASE: Final = f"{FRONTEND_URL_ROOT}/{VERSION}"
FRONTEND_DIR_NAME: Final = "frontend"
# The ?v= query string SPEC.md §7 mandates, kept alongside the versioned path.
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

# How long a bumped counter may stay in memory before it reaches the disk.
#
# The anti-spam rule collapses repeats into a counter, but collapsing them still
# produced a full rewrite of the storage file per event, because
# ``Store.async_save`` writes immediately. With a real P1 meter reporting every
# second that is a write every couple of seconds for the whole solar day —
# invisible, because the file does not grow, and real wear on the SD card or
# eMMC a Home Assistant OS install runs from.
#
# A bump is therefore kept in memory and flushed at most once per interval. A
# *new* log line still goes to disk straight away: those are rare and each one
# says something the installer has not been told yet.
LOG_FLUSH_INTERVAL_SECONDS: Final = 60

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
WS_DEVICES_SET_OPERATION: Final = f"{DOMAIN}/devices/set_operation"
WS_PREFERENCES_GET: Final = f"{DOMAIN}/preferences/get"
WS_PREFERENCES_UPDATE: Final = f"{DOMAIN}/preferences/update"
WS_COACH_GET: Final = f"{DOMAIN}/coach/get"
WS_COACH_RECALCULATE: Final = f"{DOMAIN}/coach/recalculate"
WS_LOGS_LIST: Final = f"{DOMAIN}/logs/list"
WS_LOGS_CLEAR: Final = f"{DOMAIN}/logs/clear"

ATTR_EXPECTED_REVISION: Final = "expected_revision"
ATTR_REVISION: Final = "revision"
ATTR_ITEM: Final = "item"
# Validation issues per subject, sent with every read and write answer. A
# superset of the answer shape SPEC.md §14 fixes: the documented keys are
# untouched, so a caller that ignores this one keeps working. It travels along
# rather than through a command of its own, because a second round trip after
# every save is what makes a form feel slow (SPEC.md §14).
ATTR_ISSUES: Final = "issues"

# Marks a stored source or device that the engine must never use. A row whose
# type is unrecognised keeps that type verbatim: substituting a known type
# would feed the calculations a guess, which SPEC.md §2.1 forbids.
INVALID_REASON_UNKNOWN_TYPE: Final = "unknown_type"
# Reported against a source type rather than a single row: several enabled
# sources of a type that may occur only once (EXCLUSIVE_SOURCE_TYPES).
INVALID_REASON_DUPLICATE_SOURCE: Final = "duplicate_source"
# Prefix for the logbook subject of such a report, so the anti-spam key of a
# duplicate type can never collide with a source or device id.
DUPLICATE_SUBJECT_PREFIX: Final = "duplicate:"

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

# --- Price composition (SPEC.md §8 "Woning" and §16 "Prijsopbouw") ----------
#
# What a price source actually reports. Deliberately without a default, exactly
# like METER_MODES: in the Netherlands a bare market price and an all-in price
# differ by roughly a factor of three (about EUR 0.08 against EUR 0.25), so a
# basis nobody stated is not a detail to fill in — it makes the source unusable.
# The field itself lives on the source; the components below live on the home,
# because they belong to the contract and not to the sensor.
PRICE_BASIS_ALL_IN: Final = "all_in"
PRICE_BASIS_MARKET: Final = "market"
PRICE_BASES: Final[tuple[str, ...]] = (PRICE_BASIS_ALL_IN, PRICE_BASIS_MARKET)

# A field on the home profile rather than a constant here, for the same reason
# net_metering_until is a date: the rate changes, and following it should not
# require a release.
DEFAULT_VAT_PERCENT: Final = 21.0
MIN_VAT_PERCENT: Final = 0.0
MAX_VAT_PERCENT: Final = 100.0

# Decimals the normalised all-in price is rounded to. The multiplication by the
# VAT factor otherwise leaves binary floating point noise, which would reach the
# panel verbatim; six decimals is far finer than any tariff is ever quoted.
ALL_IN_PRICE_DECIMALS: Final = 6

# --- Feed-in price composition (SPEC.md §16) --------------------------------
#
# **The import formula does not apply to feed-in, and that is the whole reason
# this is a separate source type.** An imported kWh is billed as
# (market + markup + energy tax) x (1 + VAT). A fed-in kWh earns the market
# price *minus* what the supplier keeps: no energy tax is levied on power you
# did not take, and the amount that reaches the invoice is what the customer
# gets. Reusing `all_in_price_eur_kwh` here would have overstated the feed-in
# tariff by the energy tax and the VAT on top of it — roughly threefold.
#
# The markup is subtracted, unlike the import markup which is added, because on
# this side of the meter the supplier's cut lowers what you receive.
#
# **`feed_in_markup_eur_kwh` has no default**, for the same reason the energy
# tax has none: there is no figure that is right for everyone, and a silent zero
# would overstate what the customer actually receives. A market feed-in source
# without it is refused rather than completed, and the panel says so. An
# explicit 0 is a valid answer — "this supplier keeps nothing".
#
# **Net metering ends 2027-01-01.** Until then a fed-in kWh is worth the retail
# price and this whole composition barely matters; after it, the feed-in tariff
# is the entire difference in the savings formula (SPEC.md §16).

# `default_strategy` and its four strategy constants were removed in round 1
# (SPEC.md §33.5). The field was stored, validated and rendered, and read by
# nothing — and it sat on the border of resident territory, so the role split
# would otherwise have moved it to a tab where a resident clicks it and nothing
# happens. Bring it back with a reader in the same round, or not at all.

MIN_PEAK_WARNING_PERCENT: Final = 0
MAX_PEAK_WARNING_PERCENT: Final = 100
DEFAULT_PEAK_WARNING_PERCENT: Final = 80
DEFAULT_MIN_SOLAR_SURPLUS_W: Final = 500

# --- Net metering (SPEC.md §8 "Woning" and §16) -----------------------------
#
# Dutch net metering ("saldering") ends in one step on 2027-01-01, with no
# taper. Until then a fed-in kWh is worth the full retail price, so using your
# own surplus earns nothing extra — except the feed-in cost it avoids.
#
# The date is a setting rather than a check against the calendar in code: a
# customer may have a different contract, and a date can be moved to test both
# regimes. It is a date and not a switch so the changeover happens by itself,
# instead of requiring a visit to every customer on New Year's Day 2027.
# ``None`` means this home does not have net metering at all.
DEFAULT_NET_METERING_UNTIL: Final = date(2027, 1, 1)

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

# Control modes that only make sense on hardware that can actually be driven.
# Used for the warning when the intent exceeds what the capabilities allow.
CONTROLLING_MODES: Final[tuple[str, ...]] = (
    CONTROL_APPROVAL_REQUIRED,
    CONTROL_AUTOMATIC,
)

# --- Capabilities (what the hardware can do, SPEC.md §12) -------------------
#
# Three different kinds of truth live near each other and must not be merged:
#
#   capabilities      what the hardware can do        — a property of the device
#   control_mode      what the installer wants        — an intention
#   control_forbidden what was agreed with this        — an agreement, and the
#                     customer, whatever the hardware    only one with a reason
#
# Registering only in 0.1.0: nothing is ever driven (SPEC.md §2.2). The fields
# exist now because they belong in the forms of phase 8, and adding them later
# would mean revisiting every device at every customer.

CAPABILITY_READ: Final = "read"
CAPABILITY_SWITCH: Final = "switch"
CAPABILITY_SET_POWER_LIMIT: Final = "set_power_limit"
CAPABILITY_SET_CURRENT: Final = "set_current"
CAPABILITIES: Final[tuple[str, ...]] = (
    CAPABILITY_READ,
    CAPABILITY_SWITCH,
    CAPABILITY_SET_POWER_LIMIT,
    CAPABILITY_SET_CURRENT,
)

# Everything that is more than reading a value.
CONTROL_CAPABILITIES: Final[tuple[str, ...]] = (
    CAPABILITY_SWITCH,
    CAPABILITY_SET_POWER_LIMIT,
    CAPABILITY_SET_CURRENT,
)

# --- Energy sources (SPEC.md §8 "Energiebronnen") ---------------------------

SOURCE_TYPE_GRID_METER: Final = "grid_meter"
SOURCE_TYPE_SOLAR: Final = "solar"
SOURCE_TYPE_CURRENT_PRICE: Final = "current_price"
# The feed-in tariff as a live entity, for a dynamic feed-in contract. Its own
# type rather than a flag on current_price: a home can have a dynamic import
# price and a fixed feed-in tariff, or the reverse, and the two are converted by
# different formulas (SPEC.md §16).
SOURCE_TYPE_FEED_IN_PRICE: Final = "feed_in_price"
SOURCE_TYPE_PRICE_FORECAST: Final = "price_forecast"
SOURCE_TYPE_SOLAR_FORECAST: Final = "solar_forecast"
SOURCE_TYPE_HOME_BATTERY: Final = "home_battery"
SOURCE_TYPE_GENERAL_CONSUMPTION: Final = "general_consumption"
SOURCE_TYPES: Final[tuple[str, ...]] = (
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_SOLAR,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_FEED_IN_PRICE,
    SOURCE_TYPE_PRICE_FORECAST,
    SOURCE_TYPE_SOLAR_FORECAST,
    SOURCE_TYPE_HOME_BATTERY,
    SOURCE_TYPE_GENERAL_CONSUMPTION,
)

# The source types that report a price per kWh and therefore need a
# `price_basis`. Both are normalised on reading, each by its own formula.
PRICED_SOURCE_TYPES: Final[tuple[str, ...]] = (
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_FEED_IN_PRICE,
)

# The source types whose reading is an instantaneous power in watts. Their
# allowed units are listed with the units themselves, below.
POWER_SOURCE_TYPES: Final[tuple[str, ...]] = (
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_SOLAR,
    SOURCE_TYPE_HOME_BATTERY,
    SOURCE_TYPE_GENERAL_CONSUMPTION,
)

# Source types whose readings add up when several are configured: two
# inverters really do produce more solar together.
ADDITIVE_SOURCE_TYPES: Final[tuple[str, ...]] = (
    SOURCE_TYPE_SOLAR,
    SOURCE_TYPE_GENERAL_CONSUMPTION,
    SOURCE_TYPE_HOME_BATTERY,
)

# Source types that may occur at most once. Two enabled grid meters or two
# price sources do not add up and there is no way to tell which one is meant,
# so the engine uses neither rather than picking one (SPEC.md §2.1).
EXCLUSIVE_SOURCE_TYPES: Final[tuple[str, ...]] = (
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_FEED_IN_PRICE,
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

# Multiplier from the explicitly chosen unit to the unit the engine calculates
# in: power in W, energy in Wh, price in EUR/kWh, current in A, ratio in %.
# Applied only on the basis of this choice, never on the Home Assistant
# unit_of_measurement or the entity name (SPEC.md §15). "none" means the value
# is taken as-is.
UNIT_CONVERSION_FACTORS: Final[dict[str, float]] = {
    UNIT_W: 1.0,
    UNIT_KW: 1000.0,
    UNIT_A: 1.0,
    UNIT_WH: 1.0,
    UNIT_KWH: 1000.0,
    UNIT_EUR_KWH: 1.0,
    UNIT_CT_KWH: 0.01,
    UNIT_PERCENT: 1.0,
    UNIT_NONE: 1.0,
}

# Which units describe what a source type actually measures.
#
# The unit is an explicit choice and is never derived from the entity
# (SPEC.md §15), which is right — but it also meant nothing stopped an installer
# from picking one that does not describe this kind of measurement at all. That
# is not a theoretical mistake: a Dutch P1 integration puts the cumulative
# ``energy_import`` counter in kWh far more prominently than the instantaneous
# power sensor, and linking that to a grid meter turns 12,000 kWh into
# 12,000,000 W — a permanent peak warning on a healthy house, with nothing
# anywhere to explain it. Amperes are the same trap with a smaller number:
# nothing converts them, so they are read as watts.
#
# A mismatch is a *warning*, not a refusal. It compares two explicit choices the
# installer made and says they disagree; it inspects no entity and guesses
# nothing, so it stays well inside SPEC.md §2.1.
#
# ``none`` belongs in both lists: it means "no conversion", which is a statement
# about the reading rather than a claim about its dimension.
POWER_SOURCE_UNITS: Final[tuple[str, ...]] = (UNIT_W, UNIT_KW, UNIT_NONE)
PRICE_SOURCE_UNITS: Final[tuple[str, ...]] = (UNIT_EUR_KWH, UNIT_CT_KWH, UNIT_NONE)

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

# --- Who owns which field (SPEC.md §33.4) -----------------------------------
#
# The fields on an appliance a **resident** owns, and therefore the complete
# allow-list of `devices/set_operation`. Everything else on a DeviceProfile
# belongs to the installer, so a field that is not named here is protected by
# default rather than exposed by default — a new field is safe until someone
# decides otherwise.
#
# The split runs *through* an appliance rather than around it: a dishwasher
# carries installer work (power, energy per cycle, entity links) and resident
# work (when it must be finished, on which days, may it make noise) at the same
# time. That is why this is a field list and not a per-command permission.
#
# `enabled` is deliberately absent: the resident's off switch is
# `control_mode = monitor_only`, which is what that field is for. `enabled`
# removes the row from the data quality and the engine, which is a different
# act. `is_flexible` is absent for the same kind of reason — it is a statement
# about the machine, where `is_noisy` is one about the household.
DEVICE_OPERATION_FIELDS: Final[tuple[str, ...]] = (
    "control_mode",
    "ready_from",
    "ready_before",
    "days_of_week",
    "is_noisy",
    "priority",
)

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

# --- Reading entity values (SPEC.md §15) ------------------------------------

# Clock arithmetic, used wherever a stored "HH:MM" is compared or measured.
MINUTES_PER_HOUR: Final = 60
HOURS_PER_DAY: Final = 24
MINUTES_PER_DAY: Final = MINUTES_PER_HOUR * HOURS_PER_DAY
MAX_HOUR: Final = HOURS_PER_DAY - 1
MAX_MINUTE: Final = MINUTES_PER_HOUR - 1

# States that carry no measurement. A state is refused rather than treated as
# zero: a heat pump that is unavailable is not a heat pump using 0 W.
UNUSABLE_ENTITY_STATES: Final[frozenset[str]] = frozenset(
    {STATE_UNKNOWN, STATE_UNAVAILABLE, "none", ""}
)

# --- Validation (SPEC.md §15) -----------------------------------------------

# Stable codes on a ValidationIssue. The GUI may render its own text per code;
# the Dutch message on the issue is the fallback.
VALIDATION_REQUIRED: Final = "required"
VALIDATION_OUT_OF_RANGE: Final = "out_of_range"
VALIDATION_INVALID_CHOICE: Final = "invalid_choice"
VALIDATION_INVALID_TIME_WINDOW: Final = "invalid_time_window"
VALIDATION_UNKNOWN_TYPE: Final = INVALID_REASON_UNKNOWN_TYPE
# The intended control mode needs hardware that cannot do it. A warning, not a
# block: the installer may be describing a device they are about to replace.
VALIDATION_CAPABILITY_MISSING: Final = "capability_missing"
# Control was ruled out for this installation. The only hard block among the
# three: an agreement not to touch something outranks any later intention.
VALIDATION_CONTROL_FORBIDDEN: Final = "control_forbidden"
# Not an error: SPEC.md §8 requires a warning, never a block, when the entered
# maximum grid power exceeds phases x 230 V x main fuse.
VALIDATION_ABOVE_THEORETICAL_MAXIMUM: Final = "above_theoretical_maximum"
# The chosen unit does not describe what this source type measures. A warning:
# it compares two explicit choices and finds them inconsistent, which is worth
# saying loudly but is not a reason to refuse a half-finished row.
VALIDATION_UNIT_MISMATCH: Final = "unit_mismatch"
VALIDATION_CODES: Final[tuple[str, ...]] = (
    VALIDATION_REQUIRED,
    VALIDATION_OUT_OF_RANGE,
    VALIDATION_INVALID_CHOICE,
    VALIDATION_INVALID_TIME_WINDOW,
    VALIDATION_UNKNOWN_TYPE,
    VALIDATION_ABOVE_THEORETICAL_MAXIMUM,
    VALIDATION_CAPABILITY_MISSING,
    VALIDATION_CONTROL_FORBIDDEN,
    VALIDATION_UNIT_MISMATCH,
)

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

# The three items every home is asked, because they are what the integration is
# for: without a home profile, a grid source and a price it measures nothing.
# The other three depend on the installer having said the home owns the thing.
#
# The energy score reuses this exact tuple as its gate (SPEC.md §35.7), so the
# two cannot drift apart: "the score needs a complete installation" and "these
# are the questions every installation must answer" are one statement.
COMPLETENESS_UNCONDITIONAL_ITEMS: Final = (
    COMPLETENESS_ITEM_HOME,
    COMPLETENESS_ITEM_GRID,
    COMPLETENESS_ITEM_PRICE,
)

# --- Energy score weights (SPEC.md §35) -------------------------------------

# Equal, and deliberately not split (SPEC.md §35.8). Both components answer the
# same question about the same moment — did movable consumption fall where it
# should — and the ratio only matters when both apply, which is sun plus an
# expensive hour, where they agree anyway: using your own surplus is not
# importing. Any other split would be a number nobody could defend.
SCORE_WEIGHT_SOLAR: Final = 0.50
SCORE_WEIGHT_PRICE: Final = 0.50

COMPONENT_MAX: Final = 100.0

# Below this production the solar component does not apply: at night there is
# nothing being wasted, so there is nothing to score. Not zero — a nightly zero
# was twenty points off a home that had done nothing wrong (SPEC.md §35.1).
SOLAR_COMPONENT_MIN_PRODUCTION_W: Final = 0.0

# Keys under EnergyMetrics.score_components, so the coach can show the
# breakdown behind "Hoe is mijn energiescore berekend?".
#
# **Three keys were removed in 0.4.0** and must not come back without going
# through the two rules in SPEC.md §35.1 first. `data_quality_component` and
# `flexibility_component` measured what the installer had filled in, which no
# resident can move; `peak_component` fell when the resident did what the coach
# had just advised, which is the one thing a component may never do.
SCORE_COMPONENT_SOLAR: Final = "solar_component"
SCORE_COMPONENT_PRICE: Final = "price_component"

# The weight per component, keyed the same way, so the score can divide by the
# weight of whatever actually applies instead of assuming both are present.
# Iteration order is the order the panel and the coach list them in.
SCORE_COMPONENT_WEIGHTS: Final[dict[str, float]] = {
    SCORE_COMPONENT_SOLAR: SCORE_WEIGHT_SOLAR,
    SCORE_COMPONENT_PRICE: SCORE_WEIGHT_PRICE,
}

# Why there is no score, so the panel can say *why* rather than showing a dash
# (SPEC.md §35.9). A dash reads as a fault; three of these four are not faults
# at all but descriptions of a home doing nothing wrong.
#
# Only the first is a shortcoming: the installation is incomplete and somebody
# can close it. The other three say there is nothing to optimise, which is a
# true and useful answer.
# **One code carries exactly one sentence**, which is why `nothing_right_now`
# was split into four in 0.4.2. It was a catch-all whose sentence claimed two
# measurements — "geen opwek" and "geen duur moment" — that it could not both
# guarantee, so it told a home with a fixed tariff about expensive hours it
# never has, and a home in the sun that its panels were producing nothing.
#
# Composing that sentence from fragments would have been the other way out. It
# is not taken: every variant here is written as a whole and selected by a
# situation, so each can be read, reviewed and rewritten as the sentence a
# customer actually sees (Sven, 2026-08-08).
SCORE_UNAVAILABLE_INCOMPLETE_SETUP: Final = "incomplete_setup"
SCORE_UNAVAILABLE_NO_VARIABLE_SIGNAL: Final = "no_variable_signal"
SCORE_UNAVAILABLE_NOTHING_MOVABLE: Final = "nothing_movable"
SCORE_UNAVAILABLE_NO_SUN_CHEAP_PRICE: Final = "no_sun_cheap_price"
SCORE_UNAVAILABLE_NO_SUN_FIXED_TARIFF: Final = "no_sun_fixed_tariff"
SCORE_UNAVAILABLE_CHEAP_PRICE: Final = "cheap_price"
SCORE_UNAVAILABLE_PRICE_THRESHOLDS_MISSING: Final = "price_thresholds_missing"

# Why there is no home consumption figure (SPEC.md §36.3). One code, one whole
# sentence, the same contract the tile texts follow.
#
# `battery_unreadable` deliberately withholds the number where the solar
# surplus keeps it: a charging battery shifts the surplus but is attributed
# *entirely* to the household here, so 3.5 kW would show where the house uses
# 500 W. Show a figure with a caveat while it stays usable; show nothing once
# it does not. See SPEC.md §36.3 before levelling the two.
HOME_CONSUMPTION_NO_GRID_READING: Final = "no_grid_reading"
HOME_CONSUMPTION_SOLAR_UNREADABLE: Final = "solar_unreadable"
HOME_CONSUMPTION_BATTERY_UNREADABLE: Final = "battery_unreadable"

HOME_CONSUMPTION_UNAVAILABLE_REASONS: Final = (
    HOME_CONSUMPTION_NO_GRID_READING,
    HOME_CONSUMPTION_SOLAR_UNREADABLE,
    HOME_CONSUMPTION_BATTERY_UNREADABLE,
)

SCORE_UNAVAILABLE_REASONS: Final = (
    SCORE_UNAVAILABLE_INCOMPLETE_SETUP,
    SCORE_UNAVAILABLE_NO_VARIABLE_SIGNAL,
    SCORE_UNAVAILABLE_NOTHING_MOVABLE,
    SCORE_UNAVAILABLE_NO_SUN_CHEAP_PRICE,
    SCORE_UNAVAILABLE_NO_SUN_FIXED_TARIFF,
    SCORE_UNAVAILABLE_CHEAP_PRICE,
    SCORE_UNAVAILABLE_PRICE_THRESHOLDS_MISSING,
)

SCORE_MIN: Final = 0
SCORE_MAX: Final = 100

# --- Calculation conventions (SPEC.md §16) ----------------------------------

PERCENT_MAX: Final = 100.0

# Internal sign convention for a home battery, mirroring the grid convention
# (positive = drawn from the grid): positive means charging, so the battery is
# consuming, and negative means discharging. SPEC.md §16 states that a charging
# battery counts as consumption but does not fix the sign; the installer aligns
# their entity with invert_value.
BATTERY_POSITIVE_MEANS_CHARGING: Final = True

# --- Coordinator (SPEC.md §18) ----------------------------------------------

# Two seconds was right for a slider in a test instance. A real P1 meter reports
# every second, so it meant a full recalculation every two seconds all day, and
# every threshold in the engine flipped at that rate. An advice about an
# appliance cycle does not need a two-second resolution.
RECALCULATE_DEBOUNCE_SECONDS: Final = 15.0
SAFETY_RECALCULATE_INTERVAL_MINUTES: Final = 5

# --- Hysteresis and staleness (SPEC.md §16; fixed, never configurable) -------
#
# Deliberately constants and not settings. They exist to stop a reading that
# hovers around a threshold from switching an answer on and off; that is a
# property of how the engine reads meters, not a preference a customer has an
# opinion about. A setting here would also be a setting that can be turned off.

# A peak warning switches on at the configured percentage and off only once the
# load has dropped this far below it again.
PEAK_RISK_RELEASE_MARGIN_PERCENT: Final = 5.0
# Solar advice switches on at min_solar_surplus_w and off below this fraction
# of it, so a surplus drifting around the threshold does not blink the advice —
# and with it the estimated saving — in and out of the panel.
SOLAR_SURPLUS_RELEASE_FRACTION: Final = 0.8
# Once a primary advice is shown it stays for at least this long, unless a more
# urgent one arrives or the data stops supporting it (see engine/hysteresis.py).
PRIMARY_ADVICE_MIN_DWELL_SECONDS: Final = 60.0
# A measurement older than this is refused. An entity that quietly stops
# reporting keeps its last state forever, so without this the panel shows an
# hours-old number with full confidence and the safety recalculation re-reads
# the same stale value without noticing anything (SPEC.md §15).
ENTITY_STALE_AFTER_MINUTES: Final = 15

# --- Entities (SPEC.md §19) -------------------------------------------------

ENTITY_KEY_ENERGY_SCORE: Final = "score"
ENTITY_KEY_DATA_QUALITY: Final = "data_quality"
ENTITY_KEY_GRID_POWER: Final = "grid_power"
ENTITY_KEY_SOLAR_SURPLUS: Final = "solar_surplus"
ENTITY_KEY_CURRENT_ADVICE: Final = "current_advice"
ENTITY_KEY_PEAK_RISK: Final = "peak_risk"
# Added in 0.5.0. A seventh entity is an addition, not a change: the six above
# keep their ids, so no dashboard and no statistics series breaks (rule 11).
ENTITY_KEY_HOME_CONSUMPTION: Final = "home_consumption"

ENTITY_KEYS: Final[tuple[str, ...]] = (
    ENTITY_KEY_ENERGY_SCORE,
    ENTITY_KEY_DATA_QUALITY,
    ENTITY_KEY_GRID_POWER,
    ENTITY_KEY_SOLAR_SURPLUS,
    ENTITY_KEY_CURRENT_ADVICE,
    ENTITY_KEY_PEAK_RISK,
    ENTITY_KEY_HOME_CONSUMPTION,
)

# The English entity name each object id is built from, whatever language the
# customer runs Home Assistant in. Home Assistant would otherwise derive the
# object id from the *native* name for every language in
# homeassistant.generated.languages.NATIVE_ENTITY_IDS — which contains "nl" —
# and a Dutch installation would get sensor.domotiapp_energy_energiescore.
# See entity.py for the mechanism and CLAUDE.md for why this is a hard rule.
#
# These must stay identical to the names under "entity" in translations/en.json;
# tests/test_entities.py compares the two so the duplication cannot drift.
ENTITY_OBJECT_ID_NAMES: Final[dict[str, str]] = {
    ENTITY_KEY_ENERGY_SCORE: "Score",
    ENTITY_KEY_DATA_QUALITY: "Data quality",
    ENTITY_KEY_GRID_POWER: "Grid power",
    ENTITY_KEY_SOLAR_SURPLUS: "Solar surplus",
    ENTITY_KEY_CURRENT_ADVICE: "Current advice",
    ENTITY_KEY_PEAK_RISK: "Peak risk",
    ENTITY_KEY_HOME_CONSUMPTION: "Home consumption",
}

# Home Assistant rejects a state longer than 255 characters.
MAX_STATE_LENGTH: Final = 255
# Keep the advice attributes well under the recorder/state-machine budget.
MAX_ADVICE_ITEMS_IN_ATTRIBUTES: Final = 5

# Attributes of sensor.domotiapp_energy_current_advice. The state itself is
# only the title, truncated; everything else lives here (SPEC.md §19).
ATTR_ADVICE_MESSAGE: Final = "message"
ATTR_ADVICE_REASON_CODE: Final = "reason_code"
ATTR_ADVICE_CONFIDENCE: Final = "confidence"
ATTR_ADVICE_SEVERITY: Final = "severity"
ATTR_ADVICE_MEASUREMENTS: Final = "measurements"
ATTR_ADVICE_ITEMS: Final = "advice"
ATTR_LAST_CALCULATED: Final = "last_calculated"

# --- Advice ordering (SPEC.md §16 "Sorteervolgorde") ------------------------

# 1) safety 2) peak load 3) hard time limits 4) solar 5) price 6) general.
# 0.1.0 has no safety reason code of its own; missing essential data takes that
# rank, because every other advice below it would rest on incomplete input.
ADVICE_RANK_SAFETY: Final = 1
ADVICE_RANK_PEAK: Final = 2
ADVICE_RANK_TIME_LIMIT: Final = 3
ADVICE_RANK_SOLAR: Final = 4
ADVICE_RANK_PRICE: Final = 5
ADVICE_RANK_GENERAL: Final = 6

# --- Advice measurements (SPEC.md §8 "Energiecoach") ------------------------
#
# The keys under AdviceItem.measurements. Dutch, because they surface in the
# panel and in the attributes of sensor.domotiapp_energy_current_advice, where
# customers build dashboards on them — so they are constants rather than
# literals, and they stay put. The coach adds the reading unit when it phrases
# them; see MEASUREMENT_PRICE in particular, which is always the normalised
# all-in price (SPEC.md §16).
MEASUREMENT_PRICE: Final = "prijs_eur_kwh"
MEASUREMENT_GRID_LOAD_PERCENT: Final = "netbelasting_procent"
MEASUREMENT_GRID_POWER_W: Final = "netvermogen_w"
MEASUREMENT_SOLAR_SURPLUS_W: Final = "zonneoverschot_w"
MEASUREMENT_MISSING_ITEMS: Final = "ontbrekende_onderdelen"

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
