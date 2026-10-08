from urllib.parse import urlparse
from app.database.connection import SupabaseError
from flask import Flask, g, render_template
from flask_wtf.csrf import CSRFError

from config import Config


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    key = app.config['SECRET_KEY']
    if not key or len(key) < 32 or key.startswith('REEMPLAZAR'):
        raise RuntimeError('Configura una SECRET_KEY aleatoria de al menos 32 caracteres en .env.')
    if app.config['APP_ENV'] == 'production' and not app.config['SESSION_COOKIE_SECURE']:
        raise RuntimeError('En producción debes usar HTTPS y COOKIE_SECURE=true.')
    parsed = urlparse(app.config['SUPABASE_URL'])
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path:
        raise RuntimeError('SUPABASE_URL debe ser la URL HTTPS del proyecto, sin rutas ni credenciales.')

    from app.cli import register_cli
    from app.models.torneo import PHASES, SPORTS, sport_info
    from app.models import torneo as tournament_model
    from app.routes.auth import bp as auth
    from app.routes.main import bp as main
    from app.security import csrf, load_user

    csrf.init_app(app)
    app.before_request(load_user)
    app.register_blueprint(auth)
    app.register_blueprint(main)
    register_cli(app)

    @app.context_processor
    def common_context():
        user = getattr(g, 'user', None)
        return {'user': user, 'sports': SPORTS, 'phases': PHASES, 'sport_info': sport_info,
                'nav_tournaments': tournament_model.list_tournaments() if user else []}

    @app.after_request
    def security_headers(response):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if not response.headers.get('Cache-Control'):
            response.headers['Cache-Control'] = 'no-store'
        if app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.errorhandler(SupabaseError)
    def database_error(error):
        # Sólo el código del error al log: no exponer SQL, credenciales ni datos.
        app.logger.error('Supabase no disponible (estado %s)', error.status)
        return render_template('error.html', code=503, title='No podemos conectar con los datos',
                               message='Inténtalo nuevamente en unos momentos. Si continúa, pide al administrador que revise la configuración de Supabase.'), 503

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template('error.html', code=400, title='El formulario venció',
                               message='Vuelve a abrir la página y envía el formulario nuevamente.'), 400

    for code, title, message in [
        (403, 'No tienes acceso a esta acción', 'Tu cuenta no tiene permisos para realizar esta operación.'),
        (404, 'Esta página no existe', 'Vuelve al inicio para continuar.'),
        (413, 'El archivo es demasiado grande', 'El tamaño máximo permitido es 128 KB.'),
        (500, 'No pudimos completar la operación', 'Inténtalo nuevamente. Si continúa, contacta al administrador.')]:
        def handler(error, code=code, title=title, message=message):
            return render_template('error.html', code=code, title=title, message=message), code
        app.register_error_handler(code, handler)
    return app
