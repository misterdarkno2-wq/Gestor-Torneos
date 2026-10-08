"""Sustituye páginas file:// por enlaces al servidor; originales en legacy-original/."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for original in (ROOT / 'legacy-original').glob('*.html'):
    target = 'http://127.0.0.1:5000/' + original.name
    html = f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Torneo · Abrir aplicación</title><link rel="stylesheet" href="responsive.css"></head>
<body><main><span class="eyebrow">TORNEO · DEPORTE ESCOLAR</span><h1>Tu aplicación tiene un nuevo hogar.</h1><p>Inicia el servidor con <code>python run.py</code> desde el entorno virtual y abre la aplicación para continuar.</p><a href="{target}">Abrir Torneo →</a><p class="note">Consulta README.md para configurar Supabase. Las páginas originales están respaldadas en legacy-original.</p></main></body></html>'''
    (ROOT / original.name).write_text(html, encoding='utf-8')
(ROOT / 'login.js').write_text('// El login ahora se valida en app/routes/auth.py contra Supabase.\n', encoding='utf-8')
(ROOT / 'inscripcion.js').write_text('// Las inscripciones ahora se guardan mediante app/routes/main.py.\n', encoding='utf-8')
(ROOT / 'responsive.css').write_text('''*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:#f6f7fb;color:#242338;font:16px/1.7 "Segoe UI",sans-serif}main{width:100%;max-width:560px;background:#fff;border:1px solid #e9e7f3;border-radius:24px;padding:32px;box-shadow:0 12px 50px #3027550a}h1{font-size:32px;line-height:1.2;letter-spacing:-1px}p{color:#838198}.eyebrow{font-size:10px;color:#6355d8;letter-spacing:2px;font-weight:700}a{display:inline-block;background:#6355d8;color:white;padding:12px 20px;border-radius:10px;text-decoration:none;margin:8px 0}.note{font-size:12px}code{color:#6355d8}@media(max-width:400px){main{padding:24px}h1{font-size:27px}}''', encoding='utf-8')
