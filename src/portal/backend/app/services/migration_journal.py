"""Local durable migration records; no claim of a distributed transaction."""
import json
import sqlite3
import threading
import time
from pathlib import Path


class MigrationJournal:
    def __init__(self, path=':memory:'):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        with self._db:
            self._db.execute('''CREATE TABLE IF NOT EXISTS migration_events (
                id INTEGER PRIMARY KEY, replacement TEXT NOT NULL,
                recorded_at REAL NOT NULL, payload TEXT NOT NULL)''')
            self._db.execute("CREATE TABLE IF NOT EXISTS migration_claims (replacement TEXT PRIMARY KEY)")
            self._db.execute('''CREATE INDEX IF NOT EXISTS migration_replacement
                ON migration_events(replacement, id)''')

    def start(self, replacement, result):
        """Atomically claim a replacement once, including across journal instances."""
        payload = json.dumps(result, allow_nan=False)
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT OR IGNORE INTO migration_claims(replacement) "
                "SELECT ? WHERE NOT EXISTS (SELECT 1 FROM migration_events WHERE replacement = ?)",
                (replacement, replacement))
            if cursor.rowcount != 1:
                return False
            self._db.execute("INSERT INTO migration_events (replacement, recorded_at, payload) VALUES (?, ?, ?)",
                             (replacement, time.time(), payload))
        return True

    def record(self, replacement, result):
        payload = json.dumps(result, allow_nan=False)
        with self._lock, self._db:
            self._db.execute('''INSERT INTO migration_events
                (replacement, recorded_at, payload) VALUES (?, ?, ?)''',
                (replacement, time.time(), payload))

    def get(self, replacement):
        with self._lock:
            row = self._db.execute('''SELECT payload FROM migration_events
                WHERE replacement = ? ORDER BY id DESC LIMIT 1''', (replacement,)).fetchone()
        return json.loads(row[0]) if row else None
