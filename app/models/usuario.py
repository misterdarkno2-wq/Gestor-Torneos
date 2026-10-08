"""Supabase Auth valida las contraseñas, hashes y límites de acceso."""
import json
import time
from datetime import datetime
from flask import g
from app.database.connection import SupabaseError, api
from app.database.sessions import create_session, digest, store


def authenticate(username, password, address, remember=False):
    try:
        data = api('/auth/v1/token?grant_type=password', {'email': username, 'password': password})
    except SupabaseError as exc:
        if exc.status == 429:
            return None, 'Demasiados intentos. Espera unos minutos antes de volver a intentar.'
        if exc.code == 'email_not_confirmed':
            return None, 'Confirma tu correo antes de iniciar sesión.'
        if exc.status in (400, 401, 422):
            return None, 'Correo o contraseña incorrectos.'
        raise
    data['expires_at'] = time.time() + data['expires_in']
    try:
        api('/rest/v1/rpc/gt_state', {'p_slug': None}, token=data['access_token'])
    except SupabaseError as exc:
        try:
            api('/auth/v1/logout?scope=local', {}, token=data['access_token'])
        except SupabaseError:
            pass
        if exc.code == 'PT403':
            return None, exc.public_message
        raise
    return create_session(data, remember), None


def session_user(token):
    if not token:
        return None
    with store() as db:
        row = db.execute('SELECT data FROM sessions WHERE id=?', (digest(token),)).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
    try:
        if data['expires_at'] <= time.time() + 60:
            # Sólo la renovación bloquea SQLite durante una llamada remota.
            # Releer bajo bloqueo: otro trabajador podría haber rotado el token.
            with store() as db:
                row = db.execute('SELECT data FROM sessions WHERE id=?', (digest(token),)).fetchone()
                if not row:
                    return None
                data = json.loads(row[0])
                if data['expires_at'] <= time.time() + 60:
                    data = api('/auth/v1/token?grant_type=refresh_token', {'refresh_token': data['refresh_token']})
                    data['expires_at'] = time.time() + data['expires_in']
                    db.execute('UPDATE sessions SET data=? WHERE id=?', (json.dumps(data), digest(token)))
        api('/auth/v1/user', token=data['access_token'], method='GET')
        state = api('/rest/v1/rpc/gt_state', {'p_slug': None}, token=data['access_token'])
    except SupabaseError as exc:
        if exc.status in (400, 401, 403, 422):
            with store() as db:
                db.execute('DELETE FROM sessions WHERE id=?', (digest(token),))
            return None
        raise
    g.supabase_token = data['access_token']
    for item in state.get('recent', []):
        item['created_at'] = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
    g.tournament_states = {None: state}
    return state['user']


def revoke_session(token):
    if not token:
        return
    with store() as db:
        row = db.execute('SELECT data FROM sessions WHERE id=?', (digest(token),)).fetchone()
        if row:
            try:
                api('/auth/v1/logout?scope=local', {}, token=json.loads(row[0])['access_token'])
            except SupabaseError:
                pass
        db.execute('DELETE FROM sessions WHERE id=?', (digest(token),))
