"""Verificación real de UI con datos simulados, sin tocar la base remota."""
import os
from pathlib import Path
from threading import Thread
from unittest.mock import Mock

import pytest
from werkzeug.serving import make_server

from tests.conftest import STUDENT

pytestmark = pytest.mark.skipif(os.getenv('RUN_BROWSER_TESTS') != '1', reason='Activar RUN_BROWSER_TESTS=1 para UI')


@pytest.fixture
def browser_url(app, monkeypatch):
    monkeypatch.setattr('app.routes.auth.authenticate', Mock(return_value=('ui-session', None)))
    monkeypatch.setattr('app.routes.auth.revoke_session', Mock())
    monkeypatch.setattr('app.models.torneo.edit_registration', Mock())
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        yield browser
        browser.close()


@pytest.mark.parametrize('width', [320, 375, 768, 1024, 1440, 1920])
def test_responsive_login_dashboard_and_tournament(browser, browser_url, width):
    page = browser.new_page(viewport={'width': width, 'height': 950}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
    out = Path('test-results')
    out.mkdir(exist_ok=True)
    page.goto(browser_url + '/login')
    page.locator('#usuario').fill('profesor')
    page.locator('#contrasena').fill('secure test password')
    page.get_by_role('button', name='Mostrar contraseña').click()
    assert page.locator('#contrasena').get_attribute('type') == 'text'
    page.get_by_role('button', name='Ocultar contraseña').click()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    if width in (375, 1440):
        page.screenshot(path=str(out / f'login-{width}.png'), full_page=True, animations='disabled')
    page.get_by_role('button', name='Iniciar sesión').click()
    page.wait_for_url('**/dashboard')
    assert page.get_by_role('heading', name='Hola, Andrea').is_visible()
    overflowing = page.evaluate("""[...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => ({tag:e.tagName, cls:e.className.baseVal ?? e.className, right:e.getBoundingClientRect().right, width:e.getBoundingClientRect().width}))""")
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), overflowing
    page.locator('#tournament-search').fill('volei')
    assert page.locator('[data-search]:visible').count() == 1
    page.locator('#tournament-search').fill('no-existe')
    assert page.locator('.empty-search').is_visible()
    page.locator('#tournament-search').fill('')
    if width < 900:
        page.get_by_role('button', name='Abrir menú').click()
        assert page.locator('.sidebar').get_attribute('class') == 'sidebar open'
        assert page.get_by_role('button', name='Abrir menú').get_attribute('aria-expanded') == 'true'
        page.get_by_role('button', name='Cerrar menú', exact=True).last.click()
        assert 'open' not in page.locator('.sidebar').get_attribute('class')
    if width in (375, 1440):
        page.screenshot(path=str(out / f'dashboard-{width}.png'), full_page=True, animations='disabled')
    page.goto(browser_url + '/profesor-futbol.html')
    assert page.get_by_role('heading', name='Fútbol', exact=True).is_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.get_by_role('button', name='Editar Los Cóndores', exact=True).click()
    assert page.locator('#name-1').is_visible()
    page.get_by_role('button', name='Eliminar Los Cóndores', exact=True).click()
    assert page.locator('#confirm-dialog').is_visible()
    page.get_by_role('button', name='Cancelar', exact=True).click()
    assert not page.locator('#confirm-dialog').is_visible()
    if width in (375, 1440):
        page.screenshot(path=str(out / f'torneo-{width}.png'), full_page=True, animations='disabled')
    assert errors == []
    page.close()


def test_student_menu_and_result_permissions_in_browser(browser, browser_url, monkeypatch):
    monkeypatch.setattr('app.security.session_user', lambda token: STUDENT if token else None)
    page = browser.new_page(viewport={'width': 375, 'height': 850})
    page.goto(browser_url + '/login')
    page.locator('#usuario').fill('estudiante')
    page.locator('#contrasena').fill('secure test password')
    page.get_by_role('button', name='Iniciar sesión').click()
    page.wait_for_url('**/dashboard')
    page.goto(browser_url + '/estudiante-futbol.html')
    assert page.get_by_role('button', name='Guardar resultado').count() == 0
    assert page.get_by_role('button', name='Editar Los Cóndores', exact=True).count() == 1
    assert page.get_by_role('button', name='Editar Atlético Escolar', exact=True).count() == 0
    page.get_by_role('button', name='Abrir menú').click()
    page.get_by_role('button', name='Cerrar sesión', exact=True).click()
    page.wait_for_url('**/login.html')
    page.goto(browser_url + '/dashboard')
    assert '/login' in page.url
    page.close()
