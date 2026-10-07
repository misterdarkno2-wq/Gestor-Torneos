import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.database.connection import execute, fetch_one, transaction

# Se verifica también para usuarios inexistentes para reducir diferencias de tiempo.
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32))


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def authenticate(username, password, address, remember=False):
    now = utcnow()
    # Dos límites persistentes: por usuario y por IP. No confiar en X-Forwarded-For.
    keys = sorted([digest('user:' + username), digest('ip:' + address)])
    with transaction() as cursor:
        for key in keys:
            cursor.execute('INSERT IGNORE INTO login_attempts '
                           '(attempt_key, window_started) VALUES (%s, %s)', (key, now))
        attempts = []
        for key in keys:
            cursor.execute('SELECT * FROM login_attempts WHERE attempt_key=%s FOR UPDATE', (key,))
            attempts.append(cursor.fetchone())
        if any(a['locked_until'] and a['locked_until'] > now for a in attempts):
            return None, 'Demasiados intentos. Espera 15 minutos antes de volver a intentar.'
        cursor.execute('SELECT * FROM usuarios WHERE username=%s', (username,))
        user = cursor.fetchone()
        valid = check_password_hash(user['password_hash'] if user else DUMMY_HASH, password)
        if not valid or not user or not user['activo']:
            for attempt, limit in zip(attempts, [20 if key == digest('ip:' + address) else 5 for key in keys]):
                expired = now - attempt['window_started'] >= timedelta(minutes=15)
                failures = 1 if expired else attempt['failures'] + 1
                cursor.execute('UPDATE login_attempts SET failures=%s, window_started=%s, '
                               'locked_until=%s WHERE attempt_key=%s',
                               (failures, now if expired else attempt['window_started'],
                                now + timedelta(minutes=15) if failures >= limit else None,
                                attempt['attempt_key']))
            return None, 'Usuario o contraseña incorrectos.'
        cursor.execute('DELETE FROM login_attempts WHERE attempt_key=%s', (digest('user:' + username),))
        # El límite de IP no se borra al acceder con una cuenta válida.
        token = secrets.token_urlsafe(48)
        cursor.execute('INSERT INTO auth_sessions (token_hash, usuario_id, expires_at) '
                       'VALUES (%s, %s, %s)',
                       (digest(token), user['id'], now + (timedelta(days=30) if remember else timedelta(hours=12))))
        return token, None


def session_user(token):
    if not token:
        return None
    return fetch_one('SELECT u.id, u.username, u.nombre, u.rol FROM usuarios u '
                     'JOIN auth_sessions s ON s.usuario_id=u.id '
                     'WHERE s.token_hash=%s AND s.expires_at>%s AND u.activo=TRUE',
                     (digest(token), utcnow()))


def revoke_session(token):
    if token:
        execute('DELETE FROM auth_sessions WHERE token_hash=%s', (digest(token),))


def create_user(username, nombre, password, rol):
    return execute('INSERT INTO usuarios (username, nombre, password_hash, rol) VALUES (%s,%s,%s,%s)',
                   (username, nombre, generate_password_hash(password, method='scrypt'), rol))[0]
