"""Exporta una vista pública sin importar Flask, leer .env ni consultar MySQL."""
from datetime import datetime
from pathlib import Path
from shutil import copytree
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs'
SPORTS = {
    'futbol': {'icon': 'football', 'color': 'green', 'label': 'Fútbol'},
    'basketball': {'icon': 'basketball', 'color': 'orange', 'label': 'Básquetbol'},
    'voleibol': {'icon': 'volleyball', 'color': 'purple', 'label': 'Voleibol'},
}
PHASES = {'semifinal1': 'Semifinal 1', 'semifinal2': 'Semifinal 2', 'final': 'Final'}


def sample_teams(tournament_id):
    return [
        {'id': index, 'torneo_id': tournament_id, 'usuario_id': 2 if index == 1 else 1,
         'nombre': name, 'curso': course, 'created_at': datetime(2026, 10, 7, 12)}
        for index, (name, course) in enumerate([
            ('Los Cóndores', '3° Medio A'), ('Atlético Escolar', '2° Medio B'),
            ('Los Pumas', '4° Medio A'), ('Deportivo Norte', '3° Medio B')], 1)
    ]


def sample_matches(teams):
    return [
        {'id': 1, 'fase': 'semifinal1', 'equipo_a_id': 1, 'equipo_b_id': 2,
         'equipo_a': teams[0]['nombre'], 'equipo_b': teams[1]['nombre'],
         'ganador_id': 1, 'ganador': teams[0]['nombre']},
        {'id': 2, 'fase': 'semifinal2', 'equipo_a_id': 3, 'equipo_b_id': 4,
         'equipo_a': teams[2]['nombre'], 'equipo_b': teams[3]['nombre'],
         'ganador_id': 4, 'ganador': teams[3]['nombre']},
        {'id': 3, 'fase': 'final', 'equipo_a_id': 1, 'equipo_b_id': 4,
         'equipo_a': teams[0]['nombre'], 'equipo_b': teams[3]['nombre'],
         'ganador_id': None, 'ganador': None},
    ]


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
        # Acciones del servidor: sus formularios se deshabilitan en esta vista.
        path = '#'
    return path + ('#' + quote(anchor) if anchor else '')


def build():
    OUTPUT.mkdir(exist_ok=True)
    copytree(ROOT / 'app' / 'static', OUTPUT / 'static', dirs_exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / 'app' / 'templates'),
                      autoescape=select_autoescape(['html']))
    env.globals.update(sports=SPORTS, phases=PHASES, pages_preview=True,
                       csrf_token=lambda: '', get_flashed_messages=lambda **kw: [])
    env.globals['url_for'] = lambda endpoint, **kw: static_url('estudiante', endpoint, **kw)
    for name in ('index.html', 'login.html'):
        (OUTPUT / name).write_text(env.get_template('pages_login.html').render(user=None, active=''), encoding='utf-8')
    for role in ('profesor', 'estudiante'):
        user = {'id': 1 if role == 'profesor' else 2,
                'nombre': 'Profesor Demo' if role == 'profesor' else 'Estudiante Demo', 'rol': role}
        env.globals['url_for'] = lambda endpoint, _role=role, **kw: static_url(_role, endpoint, **kw)
        tournaments = [{'id': index, 'slug': slug, 'nombre': sport['label'], 'equipos': 4, 'completados': 2}
                       for index, (slug, sport) in enumerate(SPORTS.items(), 1)]
        recent = [dict(team, deporte=tournaments[0]['nombre'], slug='futbol') for team in sample_teams(1)
                  if role == 'profesor' or team['usuario_id'] == user['id']]
        dashboard = env.get_template('dashboard.html').render(user=user, active='dashboard',
            tournaments=tournaments, recent=recent, stats={'torneos': 3, 'equipos': 12, 'resultados': 6})
        (OUTPUT / f'dashboard-{role}.html').write_text(dashboard, encoding='utf-8')
        for tournament in tournaments:
            teams = sample_teams(tournament['id'])
            html = env.get_template('tournament.html').render(user=user, active=tournament['slug'],
                tournament=tournament, teams=teams, matches=sample_matches(teams))
            (OUTPUT / f'{role}-{tournament["slug"]}.html').write_text(html, encoding='utf-8')
    env.globals['url_for'] = lambda endpoint, **kw: static_url('estudiante', endpoint, **kw)
    error_page = env.get_template('error.html').render(user=None, active='',
        code=404, title='Esta página no existe', message='Vuelve a la portada de Torneo para continuar.')
    error_page = error_page.replace('<head>', '<head>\n  <base href="/Gestor-Torneos/">', 1)
    (OUTPUT / '404.html').write_text(error_page, encoding='utf-8')
    (OUTPUT / '.nojekyll').write_text('', encoding='utf-8')
    print(f'GitHub Pages: {len(list(OUTPUT.glob("*.html")))} páginas generadas con datos ficticios.')


if __name__ == '__main__':
    build()
