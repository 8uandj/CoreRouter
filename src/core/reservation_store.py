"""Atomic local admission snapshots with one process owner per ledger path."""
import fcntl
import json
import os
import sqlite3
from pathlib import Path


class ReservationStore:
    def __init__(self, path):
        self._owner_pid = os.getpid()
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._owner = open(self.path + '.owner', 'a+')
        self._db = None
        try:
            fcntl.flock(self._owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._owner.close()
            raise RuntimeError('reservation ledger already has an owner') from exc
        try:
            self._db = sqlite3.connect(self.path, check_same_thread=False)
            with self._db:
                self._db.execute('CREATE TABLE IF NOT EXISTS reservation_snapshot '
                                 '(id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)')
        except Exception:
            self.close()
            raise

    def load(self):
        row = self._db.execute('SELECT payload FROM reservation_snapshot WHERE id = 1').fetchone()
        return json.loads(row[0]) if row else None

    def save(self, payload):
        if os.getpid() != self._owner_pid:
            raise RuntimeError("forked process cannot use parent reservation owner")
        encoded = json.dumps(payload, allow_nan=False,
                             default=lambda value: value.item())
        with self._db:
            self._db.execute('INSERT OR REPLACE INTO reservation_snapshot(id, payload) VALUES (1, ?)',
                             (encoded,))

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None
        if not self._owner.closed:
            self._owner.close()
