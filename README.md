# Torneo · Gestor de Torneos Internos

Gestión de fútbol, básquetbol y voleibol con **Supabase Auth y PostgreSQL**, interfaz responsive y roles de profesor/estudiante. Hay dos entradas a los mismos datos: el cliente de **GitHub Pages** y la aplicación **Python/Flask**. PyMySQL ya no es una dependencia.

Sitio: [Gestor de Torneos](https://misterdarkno2-wq.github.io/Gestor-Torneos/).

## Activar Supabase

La URL y clave publicable del proyecto están en `supabase/public-config.json`. Se comprobó que el servicio Auth responde; **la migración y el primer perfil todavía requieren aplicarse en el proyecto remoto**. La captura por sí sola no proporciona acceso administrativo.

1. Abre el [SQL Editor de tu proyecto](https://supabase.com/dashboard/project/mbpbukoqmsgzyilhnfay/sql/new).
2. Copia y ejecuta **completo** `supabase/migrations/202610070001_torneos.sql`. Crea tablas `gt_*`, tres deportes, funciones transaccionales y políticas RLS; conserva datos existentes. No modifica otras tablas ni opciones de Auth. Puede ejecutarse otra vez.
3. En **Authentication → Users → Add user**, crea la cuenta de acceso con correo y contraseña. Confirma el correo por el procedimiento del panel o por el mensaje de verificación; no compartas la contraseña en el repositorio.
4. En `supabase/alta-perfil.sql`, reemplaza correo y nombre, y usa rol `profesor` para el administrador o `estudiante` para el alumno. Ejecuta ese archivo para asociar la cuenta a Torneo. Si no se inserta ninguna fila, revisa el correo. Una cuenta Auth sin perfil activo no accede a esta aplicación.
5. Abre el sitio e ingresa con **correo y contraseña**. Los antiguos usuarios/contraseñas hardcoded no crean cuentas de Supabase. El rol se obtiene del perfil protegido, nunca de `user_metadata` ni de la URL.

También puede aplicarse la migración desde el plugin Supabase en Codex cuando esté conectado al proyecto. La clave publicable permite usar la app con RLS, pero no ejecutar migraciones o crear profesores.

Verificar conectividad y permisos anónimos, sin modificar datos:

```powershell
.\.venv\Scripts\python.exe scripts/check_supabase.py
```

Supabase utiliza HTTPS; no necesitas obtener un archivo CA como en la conexión MySQL anterior. El navegador y Python verifican sus certificados. Las credenciales antiguas de MySQL dejaron de utilizarse.

## Ejecutar Python/Flask

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Si ya tienes `.env`, consérvalo y actualiza sus valores. Genera una clave de sesión:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Pon el resultado en `SECRET_KEY`. Configura `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` con el mismo proyecto del cliente público. En esta entrega `.env` ya quedó actualizado localmente. No lo subas a GitHub.

```powershell
.\.venv\Scripts\python.exe run.py
```

Abre **http://127.0.0.1:5000**. Se mantienen las rutas `/dashboard`, `/torneos/futbol` y los enlaces históricos `.html`. `flask --app run init-db` indica dónde está la migración; no simula que se haya ejecutado remotamente.

Para producción Flask: HTTPS detrás de un proxy correctamente configurado, `APP_ENV=production`, `COOKIE_SECURE=true`, `TRUSTED_HOSTS` con tus dominios y protección de la carpeta `instance/`. Las sesiones están en un SQLite privado local, únicamente para tokens; los datos de los torneos permanecen en Supabase. Este almacén sirve para trabajadores en una misma máquina; varias máquinas necesitan un almacén de sesiones compartido.

## Crear cuentas desde la consola (opcional)

Para usar esta opción configura **sólo en `.env` del servidor** `SUPABASE_SECRET_KEY` con la clave administrativa de Supabase. Nunca la pongas en `public-config.json`, JavaScript, `docs/` ni GitHub. Sin esa clave usa el panel y `alta-perfil.sql`.

```powershell
.\.venv\Scripts\python.exe -m flask --app run create-user --email profesor@tucolegio.cl --nombre "Nombre Profesor" --rol profesor
```

El comando solicita la contraseña sin mostrarla. Para recuperar una cuenta utiliza Authentication en Supabase y su flujo de recuperación; no se guardan contraseñas en las tablas de Torneo.

## Actualizar GitHub Pages

GitHub Pages sirve `docs/` desde la rama `main`. El navegador usa el SDK oficial de Supabase empaquetado localmente; no requiere un servidor Python para esta versión. El login real, las inscripciones, edición, eliminación, importación, llaves y resultados llaman a las mismas funciones PostgreSQL que Flask.

```powershell
npm ci
npm run build
.\.venv\Scripts\python.exe scripts/build_pages.py
```

Después publica los cambios de `docs/` en GitHub. Si cambias URL o clave pública, edita **únicamente** `supabase/public-config.json` y vuelve a construir. La exportación no lee `.env`; sólo admite claves `sb_publishable_`. También revisa los valores de `.env` para Flask.

Enlaces:

- [Login](https://misterdarkno2-wq.github.io/Gestor-Torneos/)
- [Panel del profesor](https://misterdarkno2-wq.github.io/Gestor-Torneos/dashboard-profesor.html)
- [Panel del estudiante](https://misterdarkno2-wq.github.io/Gestor-Torneos/dashboard-estudiante.html)

Los paneles requieren sesión y redirigen al rol real de la cuenta. Los datos del ejemplo anterior se retiraron; no se importan como datos reales.

## Funciones y permisos

- Todos los miembros activos pueden ver torneos y equipos e inscribir los suyos.
- El estudiante modifica/elimina sólo sus inscripciones. El profesor administra las de la comunidad y publica llaves/resultados.
- Cada llave usa cuatro equipos del mismo deporte, con dos semifinales y una final. El ganador debe participar en el encuentro. Cambiar una semifinal actualiza los finalistas y borra el resultado anterior de la final.
- Un equipo que aparece en una llave no se elimina hasta reorganizarla. Los nombres y cursos se validan; los duplicados se comparan sin distinguir mayúsculas.
- Importar JSON es atómico, admite hasta 100 filas y 128 KB y omite duplicados. Mantiene la función para recuperar inscripciones del sistema anterior.

Las funciones SQL comprueban identidad, perfil activo, rol, propiedad y sesión de Supabase vigente. Bloquean el torneo dentro de la transacción. RLS está activado y no se conceden escrituras directas a `anon`/`authenticated`, ni permisos para que un alumno eleve su rol. Para desactivar acceso a Torneo, pon `gt_profiles.activo=false` desde administración.

Supabase Auth gestiona hashes, tokens, renovación y límites de solicitudes. Revisa **Authentication → Rate Limits** en el panel: ya no se usan los antiguos contadores MySQL de cinco intentos. Configura límites/CAPTCHA según el despliegue; no se han cambiado opciones de Auth de tu proyecto.

En Flask la cookie HttpOnly/SameSite contiene sólo un identificador aleatorio; los JWT/refresh tokens quedan en `instance/`. La sesión local vence a las 12 horas o 30 días si se recuerda. Los formularios mantienen CSRF y Jinja escapa HTML. En Pages los tokens están en `sessionStorage`, o `localStorage` al elegir Recordar sesión, con renovación mediante el SDK; la duración remota depende de la configuración de Supabase. Se aplica CSP y se escapan textos dinámicos. Cerrar sesión revoca la sesión actual de Supabase; las funciones también comprueban su registro para rechazar JWT de sesiones revocadas. Si no hay red, el cierre local se completa y se informa que falta confirmar el cierre remoto.

Referencias: [claves API de Supabase](https://supabase.com/docs/guides/getting-started/api-keys), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [login con contraseña](https://supabase.com/docs/reference/javascript/auth-signinwithpassword) y [RPC](https://supabase.com/docs/reference/javascript/rpc).

## Recuperar inscripciones anteriores

El respaldo `legacy-original/` local conserva los HTML originales. Los datos `localStorage` pertenecen al navegador y origen donde se usaron. Allí exporta un JSON por deporte desde la consola:

```javascript
for (const deporte of ['futbol', 'basketball', 'voleibol']) {
  const blob = new Blob([localStorage.getItem(deporte) || '[]'], {type: 'application/json'});
  const enlace = document.createElement('a');
  enlace.href = URL.createObjectURL(blob);
  enlace.download = `${deporte}.json`;
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
}
```

Inicia sesión en la app, abre el deporte correspondiente y usa «¿Tienes inscripciones del sistema anterior?». Los equipos se asocian a quien importa; revisa archivos de navegadores compartidos. Este procedimiento no borra los datos antiguos. No se ejecutó una migración de registros de MySQL: ese servidor no era accesible; si allí hay datos reales, conserva un respaldo antes de preparar una importación específica.

## Estructura y pruebas

`app/database/connection.py` contiene el cliente HTTPS; `app/database/sessions.py`, las sesiones privadas; `app/models/`, los adaptadores de datos; `app/routes/`, las rutas Flask; `app/templates/` y `app/static/`, la interfaz. `frontend/pages.js` es el cliente Pages, `supabase/migrations/` define reglas PostgreSQL, y `scripts/build_pages.py` genera la publicación.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
npm run test:database
$env:RUN_BROWSER_TESTS="1"
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas de SQL usan PostgreSQL en PGlite con el contexto Auth simulado. Las de navegador usan Google Chrome instalado y respuestas de Supabase simuladas: no escriben en tu proyecto. Consulta `VERIFICACION.md` para distinguir comprobaciones locales de las pendientes en el servidor remoto.
