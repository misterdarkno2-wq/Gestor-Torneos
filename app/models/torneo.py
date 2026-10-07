"""Reglas de torneos. Toda escritura bloquea el torneo antes de sus registros."""
from app.database.connection import fetch_all, fetch_one, transaction
from app.validation import clean_text

SPORTS = {
    'futbol': {'icon': 'football', 'color': 'green', 'label': 'Fútbol'},
    'basketball': {'icon': 'basketball', 'color': 'orange', 'label': 'Básquetbol'},
    'voleibol': {'icon': 'volleyball', 'color': 'purple', 'label': 'Voleibol'},
}
PHASES = {'semifinal1': 'Semifinal 1', 'semifinal2': 'Semifinal 2', 'final': 'Final'}


def list_tournaments():
    return fetch_all('SELECT t.*, (SELECT COUNT(*) FROM inscripciones i WHERE i.torneo_id=t.id) '
                     'AS equipos, (SELECT COUNT(*) FROM partidos p WHERE p.torneo_id=t.id '
                     'AND p.ganador_id IS NOT NULL) AS completados FROM torneos t ORDER BY t.id')


def get_tournament(slug):
    return fetch_one('SELECT * FROM torneos WHERE slug=%s', (slug,))


def registrations(tournament_id):
    return fetch_all('SELECT i.*, u.nombre AS creador FROM inscripciones i JOIN usuarios u '
                     'ON i.usuario_id=u.id WHERE i.torneo_id=%s ORDER BY i.created_at, i.id', (tournament_id,))


def recent_registrations(user):
    condition = '' if user['rol'] == 'profesor' else ' WHERE i.usuario_id=%s'
    params = () if user['rol'] == 'profesor' else (user['id'],)
    return fetch_all('SELECT i.*, t.nombre AS deporte, t.slug FROM inscripciones i '
                     'JOIN torneos t ON t.id=i.torneo_id' + condition + ' ORDER BY i.id DESC LIMIT 6', params)


def matches(tournament_id):
    return fetch_all('SELECT p.*, a.nombre AS equipo_a, b.nombre AS equipo_b, g.nombre AS ganador '
                     'FROM partidos p LEFT JOIN inscripciones a ON p.equipo_a_id=a.id '
                     'LEFT JOIN inscripciones b ON p.equipo_b_id=b.id '
                     'LEFT JOIN inscripciones g ON p.ganador_id=g.id '
                     'WHERE p.torneo_id=%s ORDER BY FIELD(p.fase, %s,%s,%s)',
                     (tournament_id, 'semifinal1', 'semifinal2', 'final'))


def lock_tournament(cursor, tournament_id):
    cursor.execute('SELECT id FROM torneos WHERE id=%s FOR UPDATE', (tournament_id,))
    if not cursor.fetchone():
        raise ValueError('No se encontró el torneo.')


def register(tournament_id, user_id, nombre, curso):
    nombre = clean_text(nombre, 'Nombre del equipo', 60)
    curso = clean_text(curso, 'Curso', 20, course=True)
    with transaction() as cursor:
        lock_tournament(cursor, tournament_id)
        cursor.execute('INSERT INTO inscripciones (torneo_id, usuario_id, nombre, curso) '
                       'VALUES (%s,%s,%s,%s)', (tournament_id, user_id, nombre, curso))
        return cursor.lastrowid


def edit_registration(tournament_id, registration_id, user, nombre=None, curso=None, delete=False):
    if not delete:
        nombre = clean_text(nombre or '', 'Nombre del equipo', 60)
        curso = clean_text(curso or '', 'Curso', 20, course=True)
    with transaction() as cursor:
        lock_tournament(cursor, tournament_id)
        cursor.execute('SELECT * FROM inscripciones WHERE id=%s AND torneo_id=%s FOR UPDATE',
                       (registration_id, tournament_id))
        row = cursor.fetchone()
        if not row or (user['rol'] != 'profesor' and row['usuario_id'] != user['id']):
            raise PermissionError('No puedes modificar esta inscripción.')
        if delete:
            cursor.execute('SELECT id FROM partidos WHERE torneo_id=%s AND '
                           '(equipo_a_id=%s OR equipo_b_id=%s OR ganador_id=%s) LIMIT 1',
                           (tournament_id, registration_id, registration_id, registration_id))
            if cursor.fetchone():
                raise ValueError('El equipo está en las llaves. El profesor debe reorganizarlas antes de eliminarlo.')
            cursor.execute('DELETE FROM inscripciones WHERE id=%s', (registration_id,))
        else:
            cursor.execute('UPDATE inscripciones SET nombre=%s, curso=%s WHERE id=%s',
                           (nombre, curso, registration_id))


def create_bracket(tournament_id, team_ids):
    if len(team_ids) != 4 or len(set(team_ids)) != 4:
        raise ValueError('Selecciona cuatro equipos distintos para las semifinales.')
    with transaction() as cursor:
        lock_tournament(cursor, tournament_id)
        cursor.execute('SELECT id FROM inscripciones WHERE torneo_id=%s AND id IN (%s,%s,%s,%s)',
                       (tournament_id, *team_ids))
        if len(cursor.fetchall()) != 4:
            raise ValueError('Todos los equipos deben pertenecer a este torneo.')
        cursor.execute('DELETE FROM partidos WHERE torneo_id=%s', (tournament_id,))
        for phase, a, b in [('semifinal1', team_ids[0], team_ids[1]),
                            ('semifinal2', team_ids[2], team_ids[3]), ('final', None, None)]:
            cursor.execute('INSERT INTO partidos (torneo_id, fase, equipo_a_id, equipo_b_id) '
                           'VALUES (%s,%s,%s,%s)', (tournament_id, phase, a, b))


def save_winner(tournament_id, match_id, winner_id):
    with transaction() as cursor:
        lock_tournament(cursor, tournament_id)
        cursor.execute('SELECT * FROM partidos WHERE id=%s AND torneo_id=%s FOR UPDATE',
                       (match_id, tournament_id))
        match = cursor.fetchone()
        if not match or not match['equipo_a_id'] or not match['equipo_b_id']:
            raise ValueError('El partido todavía no tiene dos equipos definidos.')
        if winner_id not in (match['equipo_a_id'], match['equipo_b_id']):
            raise ValueError('El ganador debe ser uno de los equipos de este partido.')
        if match['ganador_id'] == winner_id:
            return
        cursor.execute('UPDATE partidos SET ganador_id=%s WHERE id=%s', (winner_id, match_id))
        if match['fase'] != 'final':
            cursor.execute('SELECT fase, ganador_id FROM partidos WHERE torneo_id=%s '
                           'AND fase IN (%s,%s)', (tournament_id, 'semifinal1', 'semifinal2'))
            winners = {row['fase']: row['ganador_id'] for row in cursor.fetchall()}
            # Si cambia una semifinal, el resultado anterior de la final deja de ser válido.
            cursor.execute('UPDATE partidos SET equipo_a_id=%s, equipo_b_id=%s, ganador_id=NULL '
                           'WHERE torneo_id=%s AND fase=%s',
                           (winners.get('semifinal1'), winners.get('semifinal2'), tournament_id, 'final'))


def import_registrations(tournament_id, user_id, rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError('El archivo debe contener entre 1 y 100 inscripciones.')
    cleaned = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('nombre'), str) or not isinstance(row.get('curso'), str):
            raise ValueError('Cada inscripción necesita nombre y curso como texto.')
        cleaned.append((clean_text(row['nombre'], 'Nombre', 60), clean_text(row['curso'], 'Curso', 20, course=True)))
    inserted = 0
    with transaction() as cursor:
        lock_tournament(cursor, tournament_id)
        for nombre, curso in cleaned:
            cursor.execute('SELECT id FROM inscripciones WHERE torneo_id=%s AND nombre=%s AND curso=%s',
                           (tournament_id, nombre, curso))
            if cursor.fetchone():
                continue
            cursor.execute('INSERT INTO inscripciones (torneo_id, usuario_id, nombre, curso) '
                           'VALUES (%s,%s,%s,%s)', (tournament_id, user_id, nombre, curso))
            inserted += 1
    return inserted
