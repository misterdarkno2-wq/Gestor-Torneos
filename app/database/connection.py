"""API HTTPS de Supabase. Cada operación usa la identidad de la sesión actual."""
import requests
from flask import current_app, g


class SupabaseError(Exception):
    def __init__(self, status=503, code='', message=''):
        super().__init__('No se pudo completar la operación de Supabase.')
        self.status, self.code, self.public_message = status, code, message


def api(path, payload=None, *, token=None, method='POST', admin=False):
    config = current_app.config
    key = config['SUPABASE_SECRET_KEY'] if admin else config['SUPABASE_PUBLISHABLE_KEY']
    if not key:
        raise SupabaseError()
    headers = {'apikey': key, 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    # HTTPS verifica las CA. No reintentar escrituras que podrían estar confirmadas.
    try:
        with requests.request(method, config['SUPABASE_URL'] + path,
                              headers=headers, json=payload, timeout=(5, 15),
                              allow_redirects=False) as response:
            try:
                data = response.json() if response.content else None
            except ValueError:
                raise SupabaseError() from None
            if not 200 <= response.status_code < 300:
                data = data if isinstance(data, dict) else {}
                code = str(data.get('code') or data.get('error_code') or '')
                message = str(data.get('message', '')) if code in ('PT400', 'PT403', 'PT404') else ''
                raise SupabaseError(response.status_code, code, message)
            return data
    except requests.RequestException:
        raise SupabaseError() from None


def rpc(name, **params):
    if not getattr(g, 'supabase_token', None):
        raise PermissionError('Inicia sesión para continuar.')
    try:
        return api('/rest/v1/rpc/' + name, params, token=g.supabase_token)
    except SupabaseError as exc:
        if exc.code == 'PT403':
            raise PermissionError(exc.public_message) from None
        if exc.code in ('PT400', 'PT404'):
            raise ValueError(exc.public_message) from None
        if exc.code == '23505':
            raise ValueError('Ya existe una inscripción con ese nombre y curso en este torneo.') from None
        raise
