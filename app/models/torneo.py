"""Adaptador compatible con Flask; reglas transaccionales en PostgreSQL."""
from datetime import datetime, date
import json
import re
from pathlib import Path
from flask import g
from app.database.connection import rpc
from app.validation import clean_text

SPORTS = json.loads((Path(__file__).resolve().parents[1] / 'data/sports.json').read_text(encoding='utf-8'))
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
    return state(slug)['tournament'] if any(t['slug'] == slug for t in list_tournaments()) else None


def sport_info(tournament):
    info = dict(SPORTS.get(tournament['slug'], {'icon': 'trophy', 'color': 'purple',
                'description': 'Una nueva competencia para tu comunidad.'}))
    info['label'] = tournament['nombre']
    info['individual'] = tournament.get('modalidad', 'individual' if info.get('individual') else 'equipo') == 'individual'
    return info


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
    rows = state(tournament_slug(tournament_id))['matches']
    return sorted(rows, key=lambda row: (row.get('ronda', 2 if row['fase'] == 'final' else 1),
                                        row.get('posicion', 2 if row['fase'] == 'semifinal2' else 1)))


def bracket_rounds(rows):
    rounds = {}
    for row in rows:
        number = row.get('ronda', 2 if row['fase'] == 'final' else 1)
        rounds.setdefault(number, []).append(row)
    last = max(rounds, default=0)
    titles = {0: 'Final', 1: 'Semifinales', 2: 'Cuartos de final', 3: 'Octavos de final', 4: 'Dieciseisavos de final'}
    return [{'number': n, 'title': titles[last-n], 'matches': sorted(items, key=lambda m: m.get('posicion', 2 if m['fase'] == 'semifinal2' else 1))}
            for n, items in sorted(rounds.items())]


def register(tournament_id, user_id, nombre, curso):
    return rpc('gt_register', p_torneo=tournament_id,
               p_nombre=clean_text(nombre, 'Nombre', 60), p_curso=clean_text(curso, 'Curso', 20, course=True))


def edit_registration(tournament_id, registration_id, user, nombre=None, curso=None, delete=False):
    return rpc('gt_edit', p_torneo=tournament_id, p_id=registration_id, p_delete=delete,
               p_nombre=None if delete else clean_text(nombre or '', 'Nombre', 60),
               p_curso=None if delete else clean_text(curso or '', 'Curso', 20, course=True))


def create_bracket(tournament_id, team_ids):
    if len(team_ids) not in (4, 8, 16, 32) or len(set(team_ids)) != len(team_ids):
        raise ValueError('Selecciona 4, 8, 16 o 32 participantes distintos para las llaves.')
    return rpc('gt_bracket', p_torneo=tournament_id, p_equipos=team_ids)


def save_winner(tournament_id, match_id, winner_id):
    return rpc('gt_winner', p_torneo=tournament_id, p_partido=match_id, p_ganador=winner_id)


def manage_tournament(nombre, slug, modalidad, fecha_limite=None, abiertas=True, tournament_id=None):
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,59}', slug) or modalidad not in ('equipo', 'individual'):
        raise ValueError('Revisa el identificador y la modalidad del torneo.')
    if fecha_limite:
        try:
            date.fromisoformat(fecha_limite)
        except ValueError:
            raise ValueError('La fecha límite debe ser una fecha válida.') from None
    return rpc('gt_manage_tournament', p_nombre=clean_text(nombre, 'Nombre del torneo', 80),
               p_slug=slug, p_modalidad=modalidad, p_fecha_limite=fecha_limite or None,
               p_abiertas=abiertas, p_id=tournament_id)


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
