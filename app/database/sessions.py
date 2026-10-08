"""Tokens sólo en el servidor; cookie con identificador aleatorio.

SQLite privado en instance/ conserva sesiones entre reinicios y trabajadores.
BEGIN IMMEDIATE serializa la rotación de refresh tokens. Para varias máquinas,
reemplazar por un almacén compartido como Redis.
"""
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from flask import current_app


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


@contextmanager
def store():
    path = Path(current_app.config['SESSION_STORE'])
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=25)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, data TEXT NOT NULL, expires REAL NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM sessions WHERE expires <= ?', (time.time(),))
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_session(data, remember=False):
    token = secrets.token_urlsafe(48)
    expires = time.time() + (30 * 86400 if remember else 12 * 3600)
    with store() as db:
        db.execute('INSERT INTO sessions VALUES (?, ?, ?)', (digest(token), json.dumps(data), expires))
    return token
