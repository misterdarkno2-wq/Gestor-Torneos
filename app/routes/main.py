import json
import re

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from app.models import torneo as model
from app.security import login_required, professor_required

bp = Blueprint('main', __name__)


def tournament_or_404(slug):
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,59}', slug):
        abort(404)
    tournament = model.get_tournament(slug)
    if not tournament:
        abort(404)
    return tournament


def return_tournament(slug, anchor=''):
    return redirect(url_for('main.tournament', slug=slug, _anchor=anchor))


def report_error(exc):
    if isinstance(exc, PermissionError):
        abort(403)
    flash(str(exc), 'error')


@bp.get('/')
def index():
    return redirect(url_for('main.dashboard') if g.user else url_for('auth.login'))


@bp.get('/dashboard')
@login_required
def dashboard():
    tournaments = model.list_tournaments()
    recent = model.recent_registrations(g.user)
    stats = {'equipos': sum(t['equipos'] for t in tournaments),
             'resultados': sum(t['completados'] for t in tournaments),
             'torneos': len(tournaments)}
    return render_template('dashboard.html', tournaments=tournaments, recent=recent, stats=stats, active='dashboard')


@bp.get('/dashboard-<role>.html')
@login_required
def legacy_dashboard(role):
    if role not in ('profesor', 'estudiante'):
        abort(404)
    if g.user['rol'] != role:
        abort(403)
    return dashboard()


@bp.get('/torneos/<slug>')
@login_required
def tournament(slug):
    tournament = tournament_or_404(slug)
    return render_template('tournament.html', tournament=tournament,
                           teams=model.registrations(tournament['id']),
                           rounds=model.bracket_rounds(model.matches(tournament['id'])),
                           matches=model.matches(tournament['id']), active=slug)


@bp.get('/<role>-<slug>.html')
@login_required
def legacy_tournament(role, slug):
    if role not in ('profesor', 'estudiante'):
        abort(404)
    if role != g.user['rol']:
        abort(403)
    return tournament(slug)


@bp.post('/torneos/<slug>/inscripciones')
@login_required
def registration(slug):
    tournament = tournament_or_404(slug)
    try:
        model.register(tournament['id'], g.user['id'], request.form.get('nombre', ''), request.form.get('curso', ''))
    except (ValueError, PermissionError) as exc:
        report_error(exc)
        return return_tournament(slug, 'inscripcion')
    session['confirmation'] = {'message': 'Tu equipo quedó inscrito correctamente.', 'slug': slug}
    return redirect(url_for('main.confirmation'))


@bp.post('/torneos/<slug>/inscripciones/<int:registration_id>/<action>')
@login_required
def modify_registration(slug, registration_id, action):
    tournament = tournament_or_404(slug)
    if action not in ('editar', 'eliminar'):
        abort(404)
    try:
        model.edit_registration(tournament['id'], registration_id, g.user,
                                request.form.get('nombre', ''), request.form.get('curso', ''), delete=action == 'eliminar')
        flash('Inscripción eliminada.' if action == 'eliminar' else 'Inscripción actualizada.', 'success')
    except (ValueError, PermissionError) as exc:
        report_error(exc)
    return return_tournament(slug, 'equipos')


@bp.post('/torneos/<slug>/llaves')
@professor_required
def bracket(slug):
    tournament = tournament_or_404(slug)
    try:
        ids = [int(value) for value in request.form.getlist('equipos')]
        if request.form.get('tamano') and int(request.form['tamano']) != len(ids):
            raise ValueError('La selección debe coincidir con el tamaño de las llaves.')
        model.create_bracket(tournament['id'], ids)
        flash('Llaves guardadas. Ya puedes registrar los ganadores.', 'success')
    except (ValueError, PermissionError) as exc:
        report_error(exc)
    return return_tournament(slug, 'llaves')


@bp.post('/torneos/<slug>/partidos/<int:match_id>')
@professor_required
def result(slug, match_id):
    tournament = tournament_or_404(slug)
    try:
        winner = int(request.form.get('ganador', ''))
        model.save_winner(tournament['id'], match_id, winner)
        flash('Resultado guardado. Las siguientes rondas se actualizaron automáticamente.', 'success')
    except (ValueError, PermissionError) as exc:
        report_error(exc)
    return return_tournament(slug, 'llaves')


@bp.post('/torneos/administrar')
@professor_required
def manage_tournament():
    try:
        slug = request.form.get('slug', '')
        model.manage_tournament(request.form.get('nombre', ''), slug,
            request.form.get('modalidad', 'equipo'), request.form.get('fecha_limite') or None,
            request.form.get('abiertas') == 'on',
            int(request.form['torneo_id']) if request.form.get('torneo_id') else None)
        flash('Torneo guardado.', 'success')
        return return_tournament(slug)
    except (ValueError, PermissionError) as exc:
        report_error(exc)
        return redirect(url_for('main.dashboard'))


@bp.post('/torneos/<slug>/importar')
@login_required
def import_legacy(slug):
    tournament = tournament_or_404(slug)
    upload = request.files.get('archivo')
    try:
        if not upload:
            raise ValueError('Selecciona un archivo JSON exportado del proyecto original.')
        rows = json.loads(upload.read().decode('utf-8-sig'))
        count = model.import_registrations(tournament['id'], g.user['id'], rows)
        flash(f'Se importaron {count} inscripciones. Los duplicados se omitieron.', 'success')
    except (ValueError, UnicodeError) as exc:
        flash(str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError)
              else 'El archivo debe ser JSON válido en formato UTF-8.', 'error')
    return return_tournament(slug, 'equipos')


@bp.get('/confirmacion.html')
@login_required
def confirmation():
    confirmation = session.pop('confirmation', None)
    if not confirmation:
        return redirect(url_for('main.dashboard'))
    return render_template('confirmation.html', confirmation=confirmation, active='')
