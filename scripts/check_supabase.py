"""Comprueba configuración pública y acceso anónimo, sin crear ni modificar datos."""
import json
from pathlib import Path
import requests

public = json.loads((Path(__file__).resolve().parents[1] / 'supabase/public-config.json').read_text(encoding='utf-8'))
headers = {'apikey': public['publishableKey']}
with requests.get(public['url'] + '/auth/v1/settings', headers=headers, timeout=15) as response:
    response.raise_for_status()
    print('URL y clave publicable: correctas.')
with requests.post(public['url'] + '/rest/v1/rpc/gt_state', headers=headers, json={'p_slug': None}, timeout=15) as response:
    code = response.json().get('code', '') if response.content else ''
    if code == 'PGRST202':
        print('Pendiente: aplicar supabase/migrations/202610070001_torneos.sql.')
        raise SystemExit(2)
    if response.status_code not in (401,403):
        print('Revisa los permisos: la consulta anónima debe ser rechazada.')
        raise SystemExit(1)
    print('Funciones instaladas; acceso anónimo rechazado correctamente.')
    print('Verifica ahora un login real con una cuenta y perfil de Torneo.')
