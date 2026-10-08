"""Administración sólo desde el servidor, con clave privada local opcional."""
from pathlib import Path
import click
from flask.cli import with_appcontext
from app.database.connection import SupabaseError, api
from app.validation import clean_email, clean_text


@click.command('init-db')
def init_db():
    click.echo('Ejecuta el archivo completo en Supabase > SQL Editor:')
    click.echo(str(Path(__file__).resolve().parents[1] / 'supabase/migrations/202610070001_torneos.sql'))
    click.echo('La clave publicable no tiene permisos para aplicar migraciones.')


@click.command('create-user')
@click.option('--email', prompt='Correo')
@click.option('--nombre', prompt='Nombre visible')
@click.option('--rol', type=click.Choice(['profesor', 'estudiante']), prompt='Rol')
@click.password_option(confirmation_prompt=True, prompt='Contraseña')
@with_appcontext
def create_user_command(email, nombre, rol, password):
    try:
        email, nombre = clean_email(email), clean_text(nombre, 'Nombre', 80)
        if not 12 <= len(password) <= 128:
            raise ValueError('La contraseña debe tener entre 12 y 128 caracteres.')
        user = api('/auth/v1/admin/users', {'email': email, 'password': password,
                   'email_confirm': True}, admin=True)
        try:
            api('/rest/v1/gt_profiles', {'id': user['id'], 'nombre': nombre, 'rol': rol}, admin=True)
        except SupabaseError:
            # La cuenta Auth se conserva; completar perfil con alta-perfil.sql.
            raise click.ClickException('La cuenta Auth se creó, pero falta su perfil. Ejecuta supabase/alta-perfil.sql.') from None
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except SupabaseError:
        raise click.ClickException('Revisa Supabase y SUPABASE_SECRET_KEY local. También puedes crear la cuenta en su panel.') from None
    click.echo(f'Cuenta {email} creada con rol {rol}.')


def register_cli(app):
    app.cli.add_command(init_db)
    app.cli.add_command(create_user_command)
