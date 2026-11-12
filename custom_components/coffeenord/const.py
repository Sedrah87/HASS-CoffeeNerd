"""Konstanten der CoffeeNørd-Integration."""

DOMAIN = "coffeenord"
TITLE = "CoffeeNørd"

# Version des Upload-Formats (Feld "schema_version" im Payload).
SCHEMA_VERSION = 1
# Version des Datenbankschemas (Tabelle meta), Grundlage für spätere Migrationen.
DB_VERSION = 1
DB_DIR = "coffeenord"
DB_FILE = "shots.db"

# Grenzen für den Upload.
MAX_SHOT_BYTES = 2 * 1024 * 1024
MAX_BATCH_SHOTS = 20

STATUS_CREATED = "created"
STATUS_UPDATED = "updated"
STATUS_UNCHANGED = "unchanged"
STATUS_ERROR = "error"
