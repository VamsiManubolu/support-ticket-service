"""App-wide constants: names, paths, headers and keys shared across modules.
Keeps identifiers that clients or other layers depend on in one place."""

APP_TITLE = "Support Ticket Service"
APP_VERSION = "0.1.0"

API_V1_PREFIX = "/api/v1"
HEALTH_PATH = "/health"
HEALTH_OK = "ok"

LOCATION_HEADER = "Location"

CUSTOMER_ACTOR = "customer"
SYSTEM_ACTOR = "system"
UNKNOWN_ACTOR = "unknown"

EVENT_NOTE_KEY = "note"
