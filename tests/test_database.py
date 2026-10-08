"""Verifica HTTPS, identidad por petición, renovación y sesiones privadas."""
import json
import time
from unittest.mock import MagicMock, Mock
import pytest
import requests
from flask import g
from app.database.connection import SupabaseError, api, rpc
from app.database.sessions import create_session, digest, store
from app.models import torneo, usuario


def test_api_uses_user_identity_timeout_and_closes(app, monkeypatch):
    response = MagicMock(status_code=200, content=b'{}')
    response.json.return_value = {'ok': True}
    response.__enter__.return_value = response
    request = Mock(return_value=response)
    monkeypatch.setattr('app.database.connection.requests.request', request)
    with app.app_context():
        g.supabase_token = 'user-jwt'
        assert rpc('gt_register', p_nombre="Robert'); SQL") == {'ok': True}
    options = request.call_args.kwargs
    assert options['headers']['Authorization'] == 'Bearer user-jwt'
    assert options['json']['p_nombre'] == "Robert'); SQL"
    assert options['timeout'] == (5, 15) and options['allow_redirects'] is False
    assert 'verify' not in options  # requests verifica TLS por defecto.
    response.__exit__.assert_called_once()


def test_connection_failure_hides_credentials(app, monkeypatch):
    monkeypatch.setattr('app.database.connection.requests.request', Mock(side_effect=requests.ConnectionError('secret detail')))
    with app.app_context(), pytest.raises(SupabaseError) as error:
        api('/auth/v1/settings', method='GET')
    assert 'secret detail' not in str(error.value)


def test_rpc_translates_duplicate_and_permission_without_sql(app, monkeypatch):
    with app.app_context():
        g.supabase_token = 'jwt'
        monkeypatch.setattr('app.database.connection.api', Mock(side_effect=SupabaseError(409, '23505', 'private SQL')))
        with pytest.raises(ValueError, match='Ya existe'):
            rpc('gt_register')
        monkeypatch.setattr('app.database.connection.api', Mock(side_effect=SupabaseError(403, 'PT403', 'Sin permiso')))
        with pytest.raises(PermissionError, match='Sin permiso'):
            rpc('gt_edit')


def auth_data(expired=False):
    return {'access_token':'private-jwt','refresh_token':'private-refresh','expires_at': time.time()+(-1 if expired else 3600),'expires_in':3600}


def test_login_uses_supabase_auth_and_server_only_tokens(app, monkeypatch):
    request = Mock(side_effect=[auth_data(), {'user':{'id':'user'}}])
    monkeypatch.setattr(usuario, 'api', request)
    with app.app_context():
        token, error = usuario.authenticate('correo@example.test','password','127.0.0.1',True)
        assert token and not error and 'private-jwt' not in token
        with store() as db:
            row = db.execute('SELECT id,data,expires FROM sessions').fetchone()
        assert row[0] == digest(token) and row[0] != token
        assert 'private-refresh' in row[1] and row[2] > time.time()+29*86400
    assert request.call_args_list[0].args == ('/auth/v1/token?grant_type=password', {'email':'correo@example.test','password':'password'})


def test_refresh_rotation_and_validated_user(app, monkeypatch):
    new = {**auth_data(),'access_token':'new-jwt','refresh_token':'new-refresh'}
    request = Mock(side_effect=[new,{'id':'user'},{'user':{'id':'user','rol':'estudiante'},'recent':[]}])
    monkeypatch.setattr(usuario,'api',request)
    with app.app_context():
        token=create_session(auth_data(True))
        assert usuario.session_user(token)['id']=='user'
        assert g.supabase_token=='new-jwt'
        with store() as db:
            saved=json.loads(db.execute('SELECT data FROM sessions').fetchone()[0])
        assert saved['refresh_token']=='new-refresh'
    assert request.call_args_list[1].kwargs['method']=='GET'
    assert request.call_args_list[1].args[0]=='/auth/v1/user'


def test_invalid_refresh_clears_session_but_transient_outage_preserves_it(app, monkeypatch):
    with app.app_context():
        token=create_session(auth_data(True))
        monkeypatch.setattr(usuario,'api',Mock(side_effect=SupabaseError(503)))
        with pytest.raises(SupabaseError): usuario.session_user(token)
        with store() as db: assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==1
        monkeypatch.setattr(usuario,'api',Mock(side_effect=SupabaseError(400,'refresh_token_not_found')))
        assert usuario.session_user(token) is None
        with store() as db: assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0


def test_local_expiration_and_logout_despite_network_failure(app, monkeypatch):
    with app.app_context():
        token=create_session(auth_data())
        monkeypatch.setattr(usuario,'api',Mock(side_effect=SupabaseError()))
        usuario.revoke_session(token)
        assert usuario.session_user(token) is None
        token=create_session(auth_data())
        with store() as db: db.execute('UPDATE sessions SET expires=?',(time.time()-1,))
        assert usuario.session_user(token) is None


def test_auth_rate_limit_and_missing_profile(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(usuario,'api',Mock(side_effect=SupabaseError(429)))
        assert usuario.authenticate('u@example.test','pw','ip')[1].startswith('Demasiados')
        monkeypatch.setattr(usuario,'api',Mock(side_effect=[auth_data(),SupabaseError(403,'PT403','Sin perfil'),None]))
        assert usuario.authenticate('u@example.test','pw','ip') == (None,'Sin perfil')


def test_import_validates_all_rows_before_rpc(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(torneo,'rpc',mock)
    with pytest.raises(ValueError):
        torneo.import_registrations(1,'user',[{'nombre':'Valid Team','curso':'3 A'},{'nombre':'<script>','curso':'3 A'}])
    mock.assert_not_called()
