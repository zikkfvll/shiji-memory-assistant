"""Local storage. Raw evidence and assistance are separate collections."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def identifier():
    return uuid4().hex


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.files = self.root / 'attachments'
        self.files.mkdir(exist_ok=True)
        self.path = self.root / 'memory.sqlite3'
        self.lock = RLock()
        with self.connection() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, category TEXT NOT NULL,
                    activity_id TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS activity_documents ON documents(activity_id, category, created_at);
            ''')

    @contextmanager
    def connection(self):
        with self.lock:
            c = sqlite3.connect(self.path, timeout=10)
            try:
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()

    def put(self, category, item):
        with self.connection() as c:
            c.execute('INSERT INTO documents VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                      (item['id'], category, item.get('activity_id', item['id']), item['created_at'],
                       json.dumps(item, ensure_ascii=False)))
        return item

    def get(self, category, item_id):
        with self.connection() as c:
            row = c.execute('SELECT payload FROM documents WHERE id=? AND category=?', (item_id, category)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self, category=None, activity_id=None):
        query, args = 'SELECT payload FROM documents WHERE 1=1', []
        if category:
            query += ' AND category=?'
            args.append(category)
        if activity_id:
            query += ' AND activity_id=?'
            args.append(activity_id)
        with self.connection() as c:
            return [json.loads(r[0]) for r in c.execute(query + ' ORDER BY created_at, rowid', args)]

    def delete_activity(self, activity_id):
        with self.connection() as c:
            c.execute('DELETE FROM documents WHERE activity_id=?', (activity_id,))
