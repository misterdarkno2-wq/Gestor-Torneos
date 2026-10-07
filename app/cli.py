from pathlib import Path

import click
import pymysql
from flask.cli import with_appcontext

from app.database.connection import transaction
from werkzeug.security import generate_password_hash

from app.models.usuario import create_user, utcnow
from app.validation import clean_text, clean_username


@click.command('init-db')
@with_appcontext
def init_db():
    """Crea tablas sin borrar datos; ejecutar con un usuario de migración."""
    sql = (Path(__file__).parent / 'database' / 'schema.sql').read_text(encoding='utf-8')
    try:
        with transaction() as cursor:
            for statement in sql.split(';'):
                if statement.strip():
                    cursor.execute(statement)
            for slug, name in [('futbol', 'Fútbol'), ('basketball', 'Básquetbol'), ('voleibol', 'Voleibol')]:
                cursor.execute('INSERT INTO torneos (slug, nombre) VALUES (%s,%s) '
                               'ON DUPLICATE KEY UPDATE nombre=VALUES(nombre)', (slug, name))
    except pymysql.MySQLError as exc:
        raise click.ClickException('No se pudo inicializar MySQL. Revisa .env, acceso al servidor y permisos.') from exc
    click.echo('Tablas y tres torneos inicializados. Los datos existentes se conservaron.')


@click.command('create-user')
@click.option('--username', prompt='Usuario')
@click.option('--nombre', prompt='Nombre visible')
@click.option('--rol', type=click.Choice(['profesor', 'estudiante']), prompt='Rol')
@click.password_option(confirmation_prompt=True, prompt='Contraseña')
@with_appcontext
def create_user_command(username, nombre, rol, password):
    """Alta segura de cuentas. Nunca crea cuentas con contraseñas predeterminadas."""
    try:
        username = clean_username(username)
        nombre = clean_text(nombre, 'Nombre', 80)
        if not 12 <= len(password) <= 128:
            raise ValueError('La contraseña debe tener entre 12 y 128 caracteres.')
        create_user(username, nombre, password, rol)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except pymysql.err.IntegrityError as exc:
        raise click.ClickException('Ese usuario ya existe.') from exc
    except pymysql.MySQLError as exc:
        raise click.ClickException('No se pudo crear la cuenta. Revisa la conexión MySQL.') from exc
    click.echo(f'Cuenta {username} creada con rol {rol}.')


@click.command('cleanup-auth')
@with_appcontext
def cleanup_auth():
    """Elimina sesiones vencidas e intentos fuera de su ventana de bloqueo."""
    with transaction() as cursor:
        cursor.execute('DELETE FROM auth_sessions WHERE expires_at<=%s', (utcnow(),))
        cursor.execute('DELETE FROM login_attempts WHERE window_started < UTC_TIMESTAMP() - INTERVAL 1 DAY '
                       'AND (locked_until IS NULL OR locked_until < UTC_TIMESTAMP())')
    click.echo('Registros de autenticación vencidos eliminados.')


@click.command('reset-password')
@click.option('--username', prompt='Usuario')
@click.password_option(confirmation_prompt=True, prompt='Nueva contraseña')
@with_appcontext
def reset_password(username, password):
    """Recupera acceso y revoca sesiones. Sólo disponible por consola administrativa."""
    try:
        username = clean_username(username)
        if not 12 <= len(password) <= 128:
            raise ValueError('La contraseña debe tener entre 12 y 128 caracteres.')
        with transaction() as cursor:
            cursor.execute('SELECT id FROM usuarios WHERE username=%s FOR UPDATE', (username,))
            user = cursor.fetchone()
            if not user:
                raise ValueError('No existe ese usuario.')
            cursor.execute('UPDATE usuarios SET password_hash=%s WHERE id=%s',
                           (generate_password_hash(password, method='scrypt'), user['id']))
            cursor.execute('DELETE FROM auth_sessions WHERE usuario_id=%s', (user['id'],))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except pymysql.MySQLError as exc:
        raise click.ClickException('No se pudo cambiar la contraseña. Revisa la conexión MySQL.') from exc
    click.echo('Contraseña actualizada. Todas las sesiones de la cuenta se revocaron.')


def register_cli(app):
    app.cli.add_command(init_db)
    app.cli.add_command(create_user_command)
    app.cli.add_command(cleanup_auth)
    app.cli.add_command(reset_password)
