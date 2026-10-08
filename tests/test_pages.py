"""UI real y SDK con respuestas Supabase simuladas; ninguna escritura remota."""
import base64
import copy
import json
import os
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import pytest
from playwright.sync_api import expect
from scripts.build_pages import OUTPUT, build
from tests.conftest import MATCHES, TEAMS, TOURNAMENTS
from tests.test_browser import browser

pytestmark = pytest.mark.skipif(os.getenv('RUN_BROWSER_TESTS') != '1', reason='Activar RUN_BROWSER_TESTS=1 para UI')
UID = '10000000-0000-4000-8000-000000000001'
OTHER = '10000000-0000-4000-8000-000000000002'


@pytest.fixture
def pages_url():
    build()
    class PagesHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/Gestor-Torneos/'):
                self.path = self.path[len('/Gestor-Torneos'):]
                return super().do_GET()
            self.send_error(404)
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(PagesHandler, directory=str(OUTPUT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}/Gestor-Torneos/'
    server.shutdown(); server.server_close(); thread.join(timeout=5)


class SupabaseMock:
    def __init__(self, role='profesor'):
        self.role, self.calls = role, []
        self.tournaments = copy.deepcopy(TOURNAMENTS)
        self.teams = copy.deepcopy(TEAMS)
        for t in self.teams:
            t['usuario_id'] = UID if t['id']==1 else OTHER
            t['created_at'] = t['created_at'].isoformat()+'Z'
        self.matches = copy.deepcopy(MATCHES)
        self.fail_login = False
        self.fail_state = False

    def handle(self, route):
        request = route.request
        path = request.url.split('.supabase.co')[-1]
        headers = {'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'GET,POST,OPTIONS','access-control-expose-headers':'X-Supabase-Api-Version','x-supabase-api-version':'2024-01-01'}
        if request.method=='OPTIONS':
            route.fulfill(status=200, headers=headers, body=''); return
        payload = request.post_data_json if request.post_data else {}
        self.calls.append((path, payload))
        user = {'id':UID,'email':'cuenta@example.test','aud':'authenticated','role':'authenticated','created_at':'2026-10-07T12:00:00Z'}
        profile = {'id':UID,'nombre':'Andrea Torres','rol':self.role,'activo':True}
        status, data = 200, None
        if path.startswith('/auth/v1/token'):
            if self.fail_login: status,data=400,{'code':'invalid_credentials','msg':'Invalid login credentials'}
            else:
                encode=lambda value:base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
                token=encode({'alg':'HS256','typ':'JWT'})+'.'+encode({'sub':UID,'exp':int(time.time())+3600,'role':'authenticated','session_id':UID})+'.test-signature'
                data={'access_token':token,'refresh_token':'test-refresh','token_type':'bearer','expires_in':3600,'user':user}
        elif path == '/auth/v1/user': data=user
        elif path.startswith('/auth/v1/logout'): data={}
        elif path == '/rest/v1/rpc/gt_state':
            if self.fail_state: status,data=404,{'code':'PGRST202','message':'missing function'}
            elif payload.get('p_slug'):
                t=next(t for t in self.tournaments if t['slug']==payload['p_slug'])
                data={'user':profile,'tournament':t,'teams':[team for team in self.teams if team['torneo_id']==t['id']],'matches':self.matches if t['id']==1 or t['id']==getattr(self,'bracket_tournament',None) else []}
            else:
                recent=[dict(t,deporte='Fútbol',slug='futbol') for t in self.teams if self.role=='profesor' or t['usuario_id']==UID]
                data={'user':profile,'tournaments':self.tournaments,'recent':recent}
        elif path.endswith('/gt_register'):
            data=100
            self.teams.append({'id':100,'torneo_id':1,'usuario_id':UID,'nombre':payload['p_nombre'],'curso':payload['p_curso'],'created_at':'2026-10-07T12:00:00Z'})
        elif path.endswith('/gt_edit'):
            if payload['p_delete']: self.teams=[t for t in self.teams if t['id']!=payload['p_id']]
            else:
                t=next(t for t in self.teams if t['id']==payload['p_id']); t.update(nombre=payload['p_nombre'],curso=payload['p_curso'])
        elif path.endswith('/gt_manage_tournament'):
            if payload['p_id']:
                t=next(t for t in self.tournaments if t['id']==payload['p_id'])
            else:
                t={'id':10,'equipos':0,'completados':0,'partidos':0}; self.tournaments.append(t)
            t.update(nombre=payload['p_nombre'],slug=payload['p_slug'],modalidad=payload['p_modalidad'],fecha_limite=payload['p_fecha_limite'],inscripciones_abiertas=payload['p_abiertas'])
            data=t['id']
        elif path.endswith('/gt_import'):
            data=len(payload['p_rows'])
            for row in payload['p_rows']:
                self.teams.append({'id':max(t['id'] for t in self.teams)+1,'torneo_id':payload['p_torneo'],'usuario_id':UID,**row,'created_at':'2026-10-07T12:00:00Z'})
        elif path.endswith('/gt_bracket'):
            # API simulada; las reglas reales se comprueban en PostgreSQL.
            ids=payload['p_equipos']; size=len(ids); total=size.bit_length()-1
            self.bracket_tournament=payload['p_torneo']; self.matches=[]
            names={t['id']:t['nombre'] for t in self.teams}
            for r in range(1,total+1):
                for pos in range(1,size//(2**r)+1):
                    a,b=(ids[pos*2-2],ids[pos*2-1]) if r==1 else (None,None)
                    phase='final' if r==total else f'semifinal{pos}' if r==total-1 else f'ronda{r}_{pos}'
                    self.matches.append({'id':len(self.matches)+1,'ronda':r,'posicion':pos,'fase':phase,'equipo_a_id':a,'equipo_b_id':b,'equipo_a':names.get(a),'equipo_b':names.get(b),'ganador_id':None,'ganador':None})
            t=next(t for t in self.tournaments if t['id']==payload['p_torneo']);t['partidos']=size-1
        elif path.endswith('/gt_winner'): pass
        else: raise AssertionError('Solicitud no simulada: '+path)
        route.fulfill(status=status,content_type='application/json',headers=headers,body=json.dumps(data))


def setup(browser, fake, **options):
    context=browser.new_context(**options)
    context.route('https://*.supabase.co/**',fake.handle)
    return context


def login(page, url, remember=False):
    page.goto(url)
    page.locator('#usuario').fill('cuenta@example.test')
    page.locator('#contrasena').fill('secure test password')
    if remember: page.locator('input[name=recordar]').check()
    page.get_by_role('button',name='Iniciar sesión').click()


@pytest.mark.parametrize('width',[320,768,1440])
def test_pages_login_live_data_responsive_and_logout(browser,pages_url,width):
    fake=SupabaseMock(); context=setup(browser,fake,viewport={'width':width,'height':900})
    page=context.new_page()
    errors=[]; page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(pages_url+'profesor-futbol.html')
    page.wait_for_url('**/index.html')
    login(page,pages_url)
    page.wait_for_url('**/dashboard-profesor.html')
    expect(page.get_by_role('heading',name='Hola, Andrea')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#tournament-search').fill('futbol')
    assert page.locator('[data-search]:visible').count()==1
    page.locator('.tournament-card:visible .card-link').click()
    page.wait_for_url('**/profesor-futbol.html')
    assert page.locator('#nombre').is_enabled()
    page.locator('#nombre').fill('Nuevo Equipo'); page.locator('#curso').fill('3 A')
    page.get_by_role('button',name='Confirmar inscripción').click()
    expect(page.get_by_role('heading',name='Nuevo Equipo')).to_be_visible()
    expect(page.get_by_text('Tu equipo quedó inscrito correctamente.')).to_be_visible()
    page.get_by_role('button',name='Editar Nuevo Equipo',exact=True).click()
    page.locator('#name-100').fill('Equipo Editado')
    page.locator('#edit-100 button[type=submit]').click()
    expect(page.get_by_role('heading',name='Equipo Editado')).to_be_visible()
    page.get_by_role('button',name='Eliminar Equipo Editado',exact=True).click()
    expect(page.locator('#confirm-dialog')).to_be_visible()
    page.get_by_role('button',name='Cancelar',exact=True).click()
    expect(page.get_by_role('heading',name='Equipo Editado')).to_be_visible()
    page.get_by_role('button',name='Eliminar Equipo Editado',exact=True).click()
    page.get_by_role('button',name='Confirmar',exact=True).click()
    page.get_by_role('heading',name='Equipo Editado').wait_for(state='detached')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    Path('test-results').mkdir(exist_ok=True)
    if width in (320,1440): page.screenshot(path=f'test-results/supabase-pages-{width}.png',full_page=True,animations='disabled')
    if width<900: page.get_by_role('button',name='Abrir menú').click()
    page.get_by_role('button',name='Cerrar sesión',exact=True).click()
    page.wait_for_url('**/index.html')
    page.goto(pages_url+'dashboard-profesor.html'); page.wait_for_url('**/index.html')
    assert any(c[0].endswith('/gt_register') for c in fake.calls)
    assert errors==[]
    context.close()


def test_student_role_guard_and_html_escape(browser,pages_url):
    fake=SupabaseMock('estudiante'); fake.teams[0]['nombre']='<img src=x onerror=alert(1)>'
    context=setup(browser,fake); page=context.new_page()
    login(page,pages_url); page.wait_for_url('**/dashboard-estudiante.html')
    page.goto(pages_url+'profesor-futbol.html'); page.wait_for_url('**/estudiante-futbol.html')
    expect(page.get_by_role('heading',name='<img src=x onerror=alert(1)>',exact=True)).to_be_visible()
    assert page.locator('img[src=x]').count()==0
    assert page.get_by_role('button',name='Guardar resultado').count()==0
    assert page.get_by_role('button',name='Guardar llaves').count()==0
    assert page.get_by_role('button',name='Editar Atlético Escolar',exact=True).count()==0
    assert page.get_by_role('button',name='Editar <img src=x onerror=alert(1)>',exact=True).count()==1
    context.close()


def test_login_errors_missing_schema_and_remember_session(browser,pages_url):
    fake=SupabaseMock(); fake.fail_login=True
    context=setup(browser,fake); page=context.new_page()
    login(page,pages_url)
    expect(page.get_by_role('alert').get_by_text('Correo o contraseña incorrectos.')).to_be_visible()
    assert page.get_by_role('button',name='Iniciar sesión').is_enabled()
    fake.fail_login=False; fake.fail_state=True
    page.get_by_role('button',name='Iniciar sesión').click()
    expect(page.get_by_role('alert').get_by_text('Falta preparar las tablas de Torneo en Supabase. Contacta al administrador.')).to_be_visible()
    fake.fail_state=False
    page.locator('input[name=recordar]').check(); page.get_by_role('button',name='Iniciar sesión').click()
    page.wait_for_url('**/dashboard-profesor.html')
    another=context.new_page(); another.goto(pages_url); another.wait_for_url('**/dashboard-profesor.html')
    expect(another.get_by_role('heading',name='Hola, Andrea')).to_be_visible()
    context.close()


def test_bracket_winner_and_import_rpc_contract(browser,pages_url):
    fake=SupabaseMock(); context=setup(browser,fake); page=context.new_page()
    login(page,pages_url); page.wait_for_url('**/dashboard-profesor.html')
    page.goto(pages_url+'profesor-futbol.html')
    page.locator('#winner-1').select_option('2')
    page.locator('.result-form').first.get_by_role('button',name='Guardar resultado').click()
    page.get_by_role('button',name='Confirmar',exact=True).click()
    page.get_by_text('Resultado guardado. Las siguientes rondas se actualizaron automáticamente.').wait_for()
    page.locator('.bracket-settings summary').click()
    page.get_by_role('button',name='Guardar llaves').click()
    assert not any(c[0].endswith('/gt_bracket') for c in fake.calls)
    for box in page.locator('input[name=equipos]').all(): box.check()
    page.get_by_role('button',name='Guardar llaves').click(); page.get_by_role('button',name='Confirmar',exact=True).click()
    page.get_by_text('Llaves guardadas. Ya puedes registrar los ganadores.').wait_for()
    page.locator('.import-details summary').click()
    page.locator('#archivo').set_input_files({'name':'equipos.json','mimeType':'application/json','buffer':json.dumps([{'nombre':'Equipo Importado','curso':'3 A'}]).encode()})
    page.get_by_role('button',name='Importar inscripciones').click()
    page.get_by_text('Se importaron 1 inscripciones. Los duplicados se omitieron.').wait_for()
    winner=next(payload for path,payload in fake.calls if path.endswith('/gt_winner'))
    bracket=next(payload for path,payload in fake.calls if path.endswith('/gt_bracket'))
    assert winner=={'p_torneo':1,'p_partido':1,'p_ganador':2}
    assert bracket=={'p_torneo':1,'p_equipos':[1,2,3,4]}
    context.close()


@pytest.mark.parametrize('width',[320,1440])
def test_custom_tournament_admin_deadline_and_32_bracket(browser,pages_url,width):
    fake=SupabaseMock(); context=setup(browser,fake,viewport={'width':width,'height':900}); page=context.new_page()
    sports=json.loads(Path('app/data/sports.json').read_text(encoding='utf-8'))
    fake.tournaments=[{'id':i,'slug':slug,'nombre':sport['label'],'modalidad':'individual' if sport['individual'] else 'equipo',
        'equipos':0,'completados':0,'partidos':0} for i,(slug,sport) in enumerate(sports.items(),1)]
    errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    login(page,pages_url); page.wait_for_url('**/dashboard-profesor.html')
    expect(page.locator('.tournament-card')).to_have_count(8)
    page.locator('#tournament-name').fill('Ajedrez Primavera')
    expect(page.locator('#tournament-slug')).to_have_value('ajedrez-primavera')
    page.locator('#tournament-mode').select_option('individual')
    page.locator('#tournament-deadline').fill('2100-01-01')
    page.get_by_role('button',name='Crear torneo',exact=True).click()
    page.wait_for_url('**/profesor-torneo.html?torneo=ajedrez-primavera')
    expect(page.get_by_role('heading',name='Ajedrez Primavera',exact=True)).to_be_visible()
    expect(page.get_by_role('heading',name='Inscribe un participante',exact=True)).to_be_visible()
    page.locator('.import-details summary').click()
    rows=[{'nombre':f'Jugador {i+1}','curso':'3 A'} for i in range(32)]
    page.locator('#archivo').set_input_files({'name':'jugadores.json','mimeType':'application/json','buffer':json.dumps(rows).encode()})
    page.get_by_role('button',name='Importar inscripciones').click()
    page.get_by_text('Se importaron 32 inscripciones. Los duplicados se omitieron.').wait_for()
    page.locator('#bracket-size').select_option('32')
    for box in page.locator('input[name=equipos]').all(): box.check()
    expect(page.locator('.selection-count')).to_have_text('32 de 32 participantes seleccionados')
    page.get_by_role('button',name='Guardar llaves',exact=True).click()
    expect(page.locator('.match-card')).to_have_count(31)
    expect(page.locator('.bracket-round')).to_have_count(5)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#llaves').scroll_into_view_if_needed()
    page.screenshot(path=f'test-results/bracket-32-{width}.png',animations='disabled')
    page.locator('.tournament-admin summary').click()
    page.locator('#tournament-deadline').fill('2000-01-01')
    page.get_by_role('button',name='Guardar torneo',exact=True).click()
    expect(page.locator('#nombre')).to_be_disabled()
    expect(page.locator('.import-details button[type=submit]')).to_be_disabled()
    assert errors==[]
    create=next(payload for path,payload in fake.calls if path.endswith('/gt_manage_tournament'))
    assert create['p_id'] is None and create['p_fecha_limite']=='2100-01-01' and create['p_modalidad']=='individual'
    context.close()
