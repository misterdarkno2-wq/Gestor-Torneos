from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import MagicMock, Mock

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app.database.connection import transaction
from app.models import torneo, usuario
from tests.conftest import STUDENT


def scripted_transaction(monkeypatch, module, responses):
    cursor = MagicMock()
    cursor.fetchone.side_effect = responses
    @contextmanager
    def scripted():
        yield cursor
    monkeypatch.setattr(module, 'transaction', scripted)
    return cursor


def test_connection_commit_close_and_tls_options(app, monkeypatch):
    connection = MagicMock()
    connect = Mock(return_value=connection)
    monkeypatch.setattr('app.database.connection.pymysql.connect', connect)
    with app.app_context():
        app.config['DB_SSL_CA'] = 'provider-ca.pem'
        with transaction() as cursor:
            cursor.execute('SELECT %s', ('safe',))
    connection.commit.assert_called_once()
    connection.close.assert_called_once()
    assert connect.call_args.kwargs['ssl_verify_cert'] is True
    assert connect.call_args.kwargs['ssl_verify_identity'] is True
    assert connect.call_args.kwargs['autocommit'] is False
    connection.cursor.return_value.__exit__.assert_called_once()


def test_connection_rolls_back_and_closes_on_failure(app, monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr('app.database.connection.pymysql.connect', Mock(return_value=connection))
    with app.app_context(), pytest.raises(ValueError):
        with transaction():
            raise ValueError('failure')
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()
    connection.commit.assert_not_called()


def test_connection_without_certificate_disables_tls(app, monkeypatch):
    connect = Mock(return_value=MagicMock())
    monkeypatch.setattr('app.database.connection.pymysql.connect', connect)
    with app.app_context():
        app.config['DB_SSL_CA'] = ''
        with transaction():
            pass
    assert connect.call_args.kwargs['ssl_disabled'] is True
    assert 'ssl_ca' not in connect.call_args.kwargs


def test_password_creation_uses_hash_and_bound_values(monkeypatch):
    write = Mock(return_value=(1, 1))
    monkeypatch.setattr(usuario, 'execute', write)
    usuario.create_user('andrea', 'Andrea Torres', 'long secure password', 'profesor')
    sql, values = write.call_args.args
    assert 'long secure password' not in sql
    assert values[2].startswith('scrypt:')
    assert check_password_hash(values[2], 'long secure password')


def test_failed_auth_increments_persistent_account_and_ip_limits(monkeypatch):
    now = usuario.utcnow()
    address = '127.0.0.1'
    keys = sorted([usuario.digest('user:profesor'), usuario.digest('ip:' + address)])
    attempts = [{'attempt_key': key, 'failures': 4, 'window_started': now, 'locked_until': None} for key in keys]
    cursor = scripted_transaction(monkeypatch, usuario, [*attempts, None])
    token, error = usuario.authenticate('profesor', 'wrong', address)
    assert token is None and 'incorrectos' in error
    updates = [call.args[1] for call in cursor.execute.call_args_list if call.args[0].startswith('UPDATE login_attempts')]
    assert len(updates) == 2
    account = next(row for row in updates if row[-1] == usuario.digest('user:profesor'))
    assert account[0] == 5 and account[2] >= now + timedelta(minutes=14)


def test_locked_auth_does_not_check_password(monkeypatch):
    now = usuario.utcnow()
    attempt = {'locked_until': now + timedelta(minutes=5)}
    scripted_transaction(monkeypatch, usuario, [attempt, attempt])
    check = Mock()
    monkeypatch.setattr(usuario, 'check_password_hash', check)
    token, error = usuario.authenticate('profesor', 'wrong', '127.0.0.1')
    assert token is None and error.startswith('Demasiados')
    check.assert_not_called()


def test_successful_auth_stores_only_token_hash(monkeypatch):
    now = usuario.utcnow()
    attempt = {'locked_until': None}
    row = {'id': 1, 'activo': True, 'password_hash': generate_password_hash('valid password')}
    cursor = scripted_transaction(monkeypatch, usuario, [attempt, attempt, row])
    token, error = usuario.authenticate('profesor', 'valid password', '127.0.0.1', True)
    assert token and error is None
    stored = next(call.args[1] for call in cursor.execute.call_args_list if call.args[0].startswith('INSERT INTO auth_sessions'))
    assert stored[0] == usuario.digest(token) and stored[0] != token
    assert stored[2] > now + timedelta(days=29)


def test_student_cannot_delete_someone_elses_registration(monkeypatch):
    cursor = scripted_transaction(monkeypatch, torneo, [{'id': 1}, {'id': 7, 'usuario_id': 9}])
    with pytest.raises(PermissionError):
        torneo.edit_registration(1, 7, STUDENT, delete=True)
    assert not any(call.args[0].startswith('DELETE') for call in cursor.execute.call_args_list)


def test_team_in_bracket_cannot_be_deleted(monkeypatch):
    cursor = scripted_transaction(monkeypatch, torneo, [{'id': 1}, {'id': 7, 'usuario_id': 2}, {'id': 4}])
    with pytest.raises(ValueError, match='llaves'):
        torneo.edit_registration(1, 7, STUDENT, delete=True)
    assert not any(call.args[0].startswith('DELETE') for call in cursor.execute.call_args_list)


def test_winner_must_belong_to_match(monkeypatch):
    cursor = scripted_transaction(monkeypatch, torneo, [{'id': 1},
        {'equipo_a_id': 3, 'equipo_b_id': 4, 'ganador_id': None, 'fase': 'semifinal1'}])
    with pytest.raises(ValueError, match='uno de los equipos'):
        torneo.save_winner(1, 1, 999)
    assert not any(call.args[0].startswith('UPDATE') for call in cursor.execute.call_args_list)


def test_changed_semifinal_clears_final_and_updates_finalists(monkeypatch):
    cursor = scripted_transaction(monkeypatch, torneo, [{'id': 1},
        {'equipo_a_id': 3, 'equipo_b_id': 4, 'ganador_id': 3, 'fase': 'semifinal1'}])
    cursor.fetchall.return_value = [{'fase': 'semifinal1', 'ganador_id': 4}, {'fase': 'semifinal2', 'ganador_id': 7}]
    torneo.save_winner(1, 1, 4)
    update = cursor.execute.call_args_list[-1].args
    assert 'ganador_id=NULL' in update[0]
    assert update[1] == (4, 7, 1, 'final')


def test_bracket_does_not_accept_teams_from_another_tournament(monkeypatch):
    cursor = scripted_transaction(monkeypatch, torneo, [{'id': 1}])
    cursor.fetchall.return_value = [{'id': 1}, {'id': 2}, {'id': 3}]
    with pytest.raises(ValueError, match='pertenecer'):
        torneo.create_bracket(1, [1, 2, 3, 4])
    assert not any(call.args[0].startswith('DELETE') for call in cursor.execute.call_args_list)


def test_import_validates_all_rows_before_writing(monkeypatch):
    transaction_mock = Mock()
    monkeypatch.setattr(torneo, 'transaction', transaction_mock)
    with pytest.raises(ValueError):
        torneo.import_registrations(1, 1, [{'nombre': 'Valid Team', 'curso': '3 A'}, {'nombre': '<script>', 'curso': '3 A'}])
    transaction_mock.assert_not_called()
