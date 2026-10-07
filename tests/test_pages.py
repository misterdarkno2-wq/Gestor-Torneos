"""Comprueba la exportación y navegación bajo el prefijo real de GitHub Pages."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from scripts.build_pages import OUTPUT, build

pytestmark = pytest.mark.skipif(os.getenv('RUN_BROWSER_TESTS') != '1', reason='Activar RUN_BROWSER_TESTS=1 para UI')


@pytest.fixture
def pages_url():
    build()
    class PagesHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/Gestor-Torneos/'):
                self.path = self.path[len('/Gestor-Torneos'):]
                return super().do_GET()
            self.send_error(404)

        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(PagesHandler, directory=str(OUTPUT)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}/Gestor-Torneos/'
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.mark.parametrize('width', [320, 768, 1440])
def test_public_pages_navigation_and_readonly_forms(pages_url, width):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': width, 'height': 900})
        errors, posts = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        response = page.goto(pages_url)
        assert response.status == 200
        assert page.get_by_role('note').is_visible()
        assert page.locator('input[type=password]').count() == 0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_role('link', name='Ver panel del profesor').click()
        page.wait_for_url('**/dashboard-profesor.html')
        assert page.get_by_role('heading', name='Hola, Profesor').is_visible()
        page.locator('#tournament-search').fill('futbol')
        assert page.locator('[data-search]:visible').count() == 1
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('.tournament-card:visible .card-link').click()
        page.wait_for_url('**/profesor-futbol.html')
        assert page.locator('#nombre').is_disabled()
        assert page.get_by_role('button', name='Confirmar inscripción').is_disabled()
        assert page.get_by_role('button', name='Guardar resultado').count() == 0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        for role in ('profesor', 'estudiante'):
            for slug in ('futbol', 'basketball', 'voleibol'):
                assert page.goto(pages_url + f'{role}-{slug}.html').status == 200
                assert page.get_by_role('note').is_visible()
        page.goto(pages_url)
        page.get_by_role('link', name='Ver panel del estudiante').click()
        page.wait_for_url('**/dashboard-estudiante.html')
        assert page.get_by_role('heading', name='Hola, Estudiante').is_visible()
        out = Path('test-results')
        out.mkdir(exist_ok=True)
        if width == 1440:
            page.screenshot(path=str(out / 'github-pages-dashboard.png'), full_page=True, animations='disabled')
        assert errors == [] and posts == []
        browser.close()
