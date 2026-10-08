"""Adaptador compatible con Flask; reglas transaccionales en PostgreSQL."""
from datetime import datetime
from flask import g
from app.database.connection import rpc
from app.validation import clean_text

SPORTS = {
    'futbol': {'icon': 'football', 'color': 'green', 'label': 'Fútbol'},
    'basketball': {'icon': 'basketball', 'color': 'orange', 'label': 'Básquetbol'},
    'voleibol': {'icon': 'volleyball', 'color': 'purple', 'label': 'Voleibol'},
}
PHASES = {'semifinal1': 'Semifinal 1', 'semifinal2': 'Semifinal 2', 'final': 'Final'}


def state(slug=None):
    cache = g.setdefault('tournament_states', {})
    if slug not in cache:
        cache[slug] = rpc('gt_state', p_slug=slug)
        for row in cache[slug].get('recent', []):
            row['created_at'] = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
    return cache[slug]


def list_tournaments():
    return state()['tournaments']


def get_tournament(slug):
    return state(slug)['tournament'] if slug in SPORTS else None


def tournament_slug(tournament_id):
    for slug, data in g.get('tournament_states', {}).items():
        if slug and data['tournament']['id'] == tournament_id:
            return slug
    return next((t['slug'] for t in list_tournaments() if t['id'] == tournament_id), None)


def registrations(tournament_id):
    return state(tournament_slug(tournament_id))['teams']


def recent_registrations(user):
    return state()['recent']


def matches(tournament_id):
    return sorted(state(tournament_slug(tournament_id))['matches'], key=lambda row: list(PHASES).index(row['fase']))


def register(tournament_id, user_id, nombre, curso):
    return rpc('gt_register', p_torneo=tournament_id,
               p_nombre=clean_text(nombre, 'Nombre', 60), p_curso=clean_text(curso, 'Curso', 20, course=True))


def edit_registration(tournament_id, registration_id, user, nombre=None, curso=None, delete=False):
    return rpc('gt_edit', p_torneo=tournament_id, p_id=registration_id, p_delete=delete,
               p_nombre=None if delete else clean_text(nombre or '', 'Nombre', 60),
               p_curso=None if delete else clean_text(curso or '', 'Curso', 20, course=True))


def create_bracket(tournament_id, team_ids):
    if len(team_ids) != 4 or len(set(team_ids)) != 4:
        raise ValueError('Selecciona cuatro equipos distintos para las semifinales.')
    return rpc('gt_bracket', p_torneo=tournament_id, p_equipos=team_ids)


def save_winner(tournament_id, match_id, winner_id):
    return rpc('gt_winner', p_torneo=tournament_id, p_partido=match_id, p_ganador=winner_id)


def import_registrations(tournament_id, user_id, rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError('El archivo debe contener entre 1 y 100 inscripciones.')
    cleaned = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('nombre'), str) or not isinstance(row.get('curso'), str):
            raise ValueError('Cada inscripción necesita nombre y curso como texto.')
        cleaned.append({'nombre': clean_text(row['nombre'], 'Nombre', 60),
                        'curso': clean_text(row['curso'], 'Curso', 20, course=True)})
    return rpc('gt_import', p_torneo=tournament_id, p_rows=cleaned)
