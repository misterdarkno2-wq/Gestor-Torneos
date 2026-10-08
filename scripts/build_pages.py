"""Exporta el cliente real de Supabase. Nunca lee .env ni claves administrativas."""
import json
from pathlib import Path
from shutil import copytree
from urllib.parse import quote, urlparse
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs'
SPORTS = {
    'futbol': {'icon': 'football', 'color': 'green', 'label': 'Fútbol'},
    'basketball': {'icon': 'basketball', 'color': 'orange', 'label': 'Básquetbol'},
    'voleibol': {'icon': 'volleyball', 'color': 'purple', 'label': 'Voleibol'},
}
PHASES = {'semifinal1': 'Semifinal 1', 'semifinal2': 'Semifinal 2', 'final': 'Final'}


def static_url(role, endpoint, **values):
    anchor = values.pop('_anchor', '')
    if endpoint == 'static':
        path = 'static/' + values['filename']
    elif endpoint == 'main.dashboard':
        path = f'dashboard-{role}.html'
    elif endpoint == 'main.tournament':
        path = f'{role}-{values["slug"]}.html'
    elif endpoint in ('auth.login', 'auth.logout', 'main.index'):
        path = 'index.html'
    else:
        path = '#'
    return path + ('#' + quote(anchor) if anchor else '')


def build():
    public = json.loads((ROOT / 'supabase/public-config.json').read_text(encoding='utf-8'))
    url = urlparse(public['url'])
    if url.scheme != 'https' or not url.hostname or url.path or url.username or url.password:
        raise ValueError('Configura la URL HTTPS de Supabase.')
    if not public['publishableKey'].startswith('sb_publishable_') or len(public) != 2:
        raise ValueError('El cliente público sólo admite URL y clave sb_publishable_.')
    if not (ROOT / 'app/static/js/pages.bundle.js').exists():
        raise RuntimeError('Ejecuta npm ci y npm run build antes de exportar.')
    OUTPUT.mkdir(exist_ok=True)
    copytree(ROOT / 'app/static', OUTPUT / 'static', dirs_exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape(['html']))
    env.globals.update(sports=SPORTS, phases=PHASES, pages_preview=False, pages_live=True,
                       supabase_url=public['url'], csrf_token=lambda: '', get_flashed_messages=lambda **kw: [])
    env.globals['url_for'] = lambda endpoint, **kw: static_url('estudiante', endpoint, **kw)
    for name in ('index.html', 'login.html'):
        (OUTPUT / name).write_text(env.get_template('login.html').render(user=None, username='', error=None, active=''), encoding='utf-8')
    for role in ('profesor', 'estudiante'):
        user = {'id': '', 'nombre': 'Cuenta', 'rol': role}
        env.globals['url_for'] = lambda endpoint, _role=role, **kw: static_url(_role, endpoint, **kw)
        tournaments = [{'id': index, 'slug': slug, 'nombre': sport['label'], 'equipos': 0, 'completados': 0}
                       for index, (slug, sport) in enumerate(SPORTS.items(), 1)]
        html = env.get_template('dashboard.html').render(user=user, active='dashboard',
            tournaments=tournaments, recent=[], stats={'torneos': 0, 'equipos': 0, 'resultados': 0})
        (OUTPUT / f'dashboard-{role}.html').write_text(html, encoding='utf-8')
        for tournament in tournaments:
            html = env.get_template('tournament.html').render(user=user, active=tournament['slug'],
                tournament=tournament, teams=[], matches=[])
            (OUTPUT / f'{role}-{tournament["slug"]}.html').write_text(html, encoding='utf-8')
    # La confirmación real se muestra después de guardar; esta URL antigua vuelve al resumen.
    (OUTPUT / 'confirmacion.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>Torneo</title><meta http-equiv="refresh" content="0;url=index.html"><a href="index.html">Continuar</a></html>', encoding='utf-8')
    env.globals['url_for'] = lambda endpoint, **kw: static_url('estudiante', endpoint, **kw)
    error = env.get_template('error.html').render(user=None, active='', code=404,
                title='Esta página no existe', message='Vuelve al inicio de Torneo para continuar.')
    error = error.replace('<head>', '<head>\n  <base href="/Gestor-Torneos/">', 1)
    (OUTPUT / '404.html').write_text(error, encoding='utf-8')
    (OUTPUT / '.nojekyll').write_text('', encoding='utf-8')
    for page in OUTPUT.glob('*.html'):
        page.write_text('\n'.join(line.rstrip() for line in page.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    print('GitHub Pages: cliente Supabase generado; sin datos de demostración.')


if __name__ == '__main__':
    build()
