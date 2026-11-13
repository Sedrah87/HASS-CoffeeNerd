"""Konstanten der CoffeeNørd-Integration."""

DOMAIN = "coffeenord"
TITLE = "CoffeeNørd"

# Version des Upload-Formats (Feld "schema_version" im Payload).
SCHEMA_VERSION = 1
# Version des Datenbankschemas (Tabelle meta), Grundlage für spätere Migrationen.
DB_VERSION = 2
DB_DIR = "coffeenord"
DB_FILE = "shots.db"

# Grenzen für den Upload.
MAX_SHOT_BYTES = 2 * 1024 * 1024
MAX_BATCH_SHOTS = 20

STATUS_CREATED = "created"
STATUS_UPDATED = "updated"
STATUS_UNCHANGED = "unchanged"
STATUS_ERROR = "error"

# Event für Automationen, z. B. „Maschine nach dem Shot in den Standby“.
EVENT_SHOT_RECEIVED = "coffeenord_shot_received"
# Nur für Shots, die höchstens so alt sind. Der Erst-Import alter Brews würde
# Automationen sonst hundertfach auslösen.
EVENT_MAX_AGE_SECONDS = 3600
# Dispatcher-Signal: Ein Shot wurde gespeichert oder gelöscht.
SIGNAL_SHOTS_CHANGED = f"{DOMAIN}_shots_changed"
