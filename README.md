# Torneo · Gestor de Torneos Internos

Aplicación Flask para torneos escolares de **fútbol, básquetbol y voleibol**, con cuentas de profesor y estudiante, MySQL mediante PyMySQL y una interfaz responsive.

## Sitio público en GitHub Pages

Dirección: **https://misterdarkno2-wq.github.io/Gestor-Torneos/**.

GitHub Pages publica la carpeta `docs/` de la rama `main`. Esta versión permite explorar los paneles y torneos con **datos ficticios**. No solicita contraseñas y mantiene los formularios de inscripción deshabilitados. La navegación, el menú móvil y la búsqueda sí funcionan.

Pages sirve archivos estáticos y no ejecuta Flask ni conecta con MySQL. Para utilizar login, inscripciones y resultados reales, ejecuta la aplicación con servidor siguiendo las instrucciones de este documento. Consulta la [documentación de GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).

Para actualizar la versión pública después de cambiar plantillas o estilos:

```powershell
.\.venv\Scripts\python.exe scripts/build_pages.py
git add docs app scripts
git commit -m "Actualizar sitio público"
git push origin main
```

La exportación sólo copia los recursos públicos y renderiza datos de ejemplo; no lee `.env` ni consulta la base de datos. GitHub Pages vuelve a publicar al subir cambios en `docs/`.

## Diagnóstico del proyecto original

La carpeta recibida no contenía Python, Flask, Django ni una base de datos: eran once archivos HTML, dos scripts y una hoja CSS. El login comparaba credenciales públicas (`profesor` / `estudiante`) en JavaScript, no creaba sesiones ni protegía páginas. Los estudiantes guardaban inscripciones en `localStorage`; los formularios del profesor sólo abrían una confirmación y las llaves eran ejemplos estáticos. La misma presentación se repetía en cada HTML.

Se incorporó Flask sin quitar los dos roles, las tres disciplinas, la inscripción, las semifinales, la final, la edición de resultados ni la confirmación. Las páginas originales están copiadas sin cambios en `legacy-original/` en el equipo de origen; este respaldo se excluye de GitHub. Las URLs `.html` siguen funcionando a través del servidor con control de acceso por rol. Abrir los HTML con doble clic ahora muestra instrucciones para entrar al servidor: la aplicación necesita ejecutarse con Python.

## Archivos y responsabilidades

```text
app/
  __init__.py              fábrica Flask, errores y cabeceras de seguridad
  cli.py                   inicialización de tablas y alta de usuarios
  security.py              CSRF, sesión y permisos por rol
  validation.py            validación compartida en servidor
  database/
    connection.py          PyMySQL, consultas parametrizadas, transacciones
    schema.sql             esquema MySQL/InnoDB/utf8mb4
  models/
    usuario.py             hash scrypt, bloqueos y sesiones revocables
    torneo.py              CRUD, importación, llaves y resultados
  routes/
    auth.py                login y logout
    main.py                dashboard, deportes e inscripciones
  templates/               vistas Jinja con escape HTML automático
  static/css/app.css       diseño móvil y escritorio
  static/js/app.js         menú, búsqueda, confirmaciones y estados de carga
  static/images/logo.svg   logo local
config.py                  configuración de entorno
run.py                     entrada con Waitress, sin depurador
.env                       configuración privada local; no versionar
.env.example               plantilla sin credenciales
requirements.txt           dependencias de ejecución
requirements-dev.txt       dependencias para pruebas
tests/                     seguridad, reglas, navegador y MySQL opcional
legacy-original/           respaldo local del proyecto recibido; excluido de Git
```

## 1. Instalar (Python 3.10 o superior)

En PowerShell, desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

En esta entrega ya se creó `.venv`, se instalaron las dependencias y se generó una `SECRET_KEY` aleatoria dentro de `.env`. No hay cuentas ni contraseñas predeterminadas.

En otra máquina, copia `.env.example` a `.env` y genera la clave:

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Pega el resultado en `SECRET_KEY`. No reemplaces una clave existente si quieres conservar sesiones. Nunca publiques `.env`.

## 2. Preparar tu MySQL remoto

Pide al administrador/proveedor una base **dedicada** MySQL 8.0 o superior y acceso desde la IP de este equipo. Si el servidor usa TLS, solicita el certificado CA. En desarrollo también se admiten servidores sin TLS dejando `DB_SSL_CA` vacío. No hay credenciales del servidor remoto en esta carpeta.

El administrador puede ejecutar lo siguiente en MySQL, reemplazando la IP de origen y la contraseña. La contraseña es un marcador y debe cambiarse antes de ejecutar:

Este ejemplo utiliza TLS. Para un servidor de desarrollo sin TLS, omite `REQUIRE SSL` en las instrucciones `CREATE USER`.

```sql
CREATE DATABASE IF NOT EXISTS gestor_torneos
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'torneos_migracion'@'IP_DEL_EQUIPO'
  IDENTIFIED BY 'REEMPLAZAR_POR_UNA_CONTRASENA_UNICA' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, REFERENCES
  ON gestor_torneos.* TO 'torneos_migracion'@'IP_DEL_EQUIPO';

CREATE USER 'torneos_app'@'IP_DEL_EQUIPO'
  IDENTIFIED BY 'REEMPLAZAR_POR_OTRA_CONTRASENA_UNICA' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON gestor_torneos.* TO 'torneos_app'@'IP_DEL_EQUIPO';
```

En servicios administrados, crea la base y los usuarios mediante el panel del proveedor si no tienes permiso para estos comandos. Usa una base sin tablas previas con estos nombres; `init-db` no transforma esquemas ajenos o de versiones anteriores.

Edita **localmente** `.env`:

```dotenv
APP_ENV=development
SECRET_KEY=TU_CLAVE_ALEATORIA
DB_HOST=nombre-real-del-servidor
DB_USER=torneos_migracion
DB_PASSWORD=CONTRASENA_REAL
DB_NAME=gestor_torneos
DB_PORT=3306
DB_SSL_CA=C:/certificados/ca-del-proveedor.pem
COOKIE_SECURE=false
TRUSTED_HOSTS=localhost,127.0.0.1
PORT=5000
```

Cuando `DB_SSL_CA` contiene una ruta, PyMySQL verifica tanto la CA como la identidad del servidor y `DB_HOST` debe coincidir con el nombre del certificado. En desarrollo puedes dejar `DB_SSL_CA=` para conectar a un servidor sin TLS. La aplicación exige certificado para MySQL remoto cuando `APP_ENV=production`. Usa rutas Windows con `/`. Si una contraseña contiene `#` o espacios, escríbela entre comillas en `.env`.

Inicializa las tablas (no borra datos; MySQL hace commit implícito al ejecutar DDL):

```powershell
.\.venv\Scripts\python.exe -m flask --app run init-db
```

Después cambia `DB_USER` y `DB_PASSWORD` a los de **torneos_app** para el uso habitual. La aplicación no necesita permisos para crear tablas durante su ejecución.

## 3. Crear las cuentas

```powershell
.\.venv\Scripts\python.exe -m flask --app run create-user --username profesor --nombre "Profesor Principal" --rol profesor
.\.venv\Scripts\python.exe -m flask --app run create-user --username estudiante --nombre "Estudiante Principal" --rol estudiante
```

Se solicita y confirma la contraseña de forma oculta. Debe tener entre 12 y 128 caracteres. Se guarda exclusivamente el hash scrypt de Werkzeug. No uses las contraseñas antiguas `1234`.

Para restablecer el acceso de una cuenta existente, ejecuta:

```powershell
.\.venv\Scripts\python.exe -m flask --app run reset-password --username profesor
```

Se pide una nueva contraseña y se revocan todas las sesiones de esa cuenta.

## 4. Ejecutar

```powershell
.\.venv\Scripts\python.exe run.py
```

Abre **http://127.0.0.1:5000**. Waitress escucha únicamente en este equipo. Si cambias `PORT`, usa ese puerto en el navegador; los enlaces de los HTML de entrada apuntan al puerto predeterminado 5000.

Para publicar en un servidor, configura un proxy HTTPS hacia Waitress y actualiza `APP_ENV=production`, `COOKIE_SECURE=true` y `TRUSTED_HOSTS=tu-dominio-real`. Configura un `SECRET_KEY` privado y persistente. No sirvas la carpeta raíz con un servidor estático: únicamente Flask debe servir `app/static/` y las vistas. El respaldo `legacy-original/` contiene el antiguo login y debe permanecer fuera del sitio público.

## Funciones y reglas

- **Profesor:** consulta los tres torneos; registra, edita y elimina inscripciones; selecciona cuatro equipos para semifinales; guarda y modifica ganadores. Puede ver toda la actividad.
- **Estudiante:** consulta equipos y llaves; registra equipos; edita y elimina únicamente sus inscripciones. Su resumen muestra su actividad reciente.
- Se pueden registrar más de cuatro equipos. Las llaves mantienen el formato original de dos semifinales y una final; el profesor escoge los cuatro participantes en el orden de la lista.
- El ganador debe pertenecer al partido. La final recibe automáticamente los ganadores de las semifinales. Cambiar una semifinal borra el resultado anterior de la final. Guardar de nuevo el mismo ganador conserva la final.
- Reorganizar las llaves pide confirmación y reemplaza los partidos/resultados del torneo. Los equipos participantes no se pueden eliminar mientras estén en las llaves; el profesor debe reorganizarlas con otros equipos.
- Nombre del equipo: de 2 a 60 letras, números y espacios. Curso: de 2 a 20 caracteres, también admite ° y guiones. Se rechazan duplicados de nombre + curso dentro de un deporte.
- Las eliminaciones y cambios de llaves tienen confirmación; los formularios muestran estado de carga y avisos. La búsqueda de deportes funciona con y sin acentos.

## Sesiones y seguridad

Los formularios POST tienen CSRF. Las consultas reciben valores parametrizados y cierran cursores/conexiones incluso ante errores. Los cambios de inscripciones, llaves y resultados bloquean su torneo dentro de una transacción para evitar carreras.

La cookie firmada no incluye contraseña ni hash; contiene un token aleatorio cuya huella SHA-256 se guarda en MySQL. La sesión normal dura hasta 12 horas y la recordada hasta 30 días; el servidor impone la expiración y permite revocación al cerrar sesión. Desactivar `usuarios.activo` corta el acceso de la cuenta.

Se limita el acceso fallido por usuario (5 intentos) y por IP (20 intentos), con ventana/bloqueo de 15 minutos, persistente en MySQL. Acceder correctamente no limpia el contador de IP. No se confía en cabeceras de IP enviadas por el cliente. Detrás de un proxy, los usuarios comparten la IP del proxy hasta configurar conscientemente el proxy de confianza; no habilites confianza indiscriminada en `X-Forwarded-For`.

Para limpiar registros de autenticación vencidos:

```powershell
.\.venv\Scripts\python.exe -m flask --app run cleanup-auth
```

Los recursos gráficos, estilos e iconos son locales. Jinja escapa el contenido HTML y la aplicación envía CSP, protección contra iframes y cookies HttpOnly/SameSite. Un fallo de MySQL devuelve 503 con un mensaje claro, sin exponer detalles de conexión.

Estas decisiones siguen las guías oficiales de [seguridad de Flask](https://flask.palletsprojects.com/en/stable/web-security/) y [consultas parametrizadas/transacciones de PyMySQL](https://pymysql.readthedocs.io/en/latest/user/examples.html).

## Recuperar inscripciones del navegador anterior

Los datos `localStorage` dependen del navegador y del origen donde usaste el proyecto; una página `file://` no comparte esos datos automáticamente con Flask. El respaldo no modifica ni borra los datos del navegador.

1. Abre una página de estudiante en `legacy-original/` en el **mismo navegador y origen** del proyecto original. Si los datos sólo aparecen en la ubicación original, abre esa página original de entrada antes de exportar. Las páginas de entrada no borran `localStorage`.
2. En las herramientas de desarrollador, pestaña Consola, ejecuta el siguiente código. Sólo lee las tres claves de torneos y descarga un JSON por deporte; no envía información a ningún servidor.
3. Inicia sesión en Flask, abre el deporte correspondiente y despliega «¿Tienes inscripciones del sistema anterior?». Selecciona su JSON y pulsa **Importar inscripciones**. Cada archivo puede contener hasta 100 filas y pesar hasta 128 KB. Valida todas las filas antes de guardar y omite duplicados.

```javascript
for (const deporte of ['futbol', 'basketball', 'voleibol']) {
  const contenido = localStorage.getItem(deporte) || '[]';
  const blob = new Blob([contenido], {type: 'application/json'});
  const enlace = document.createElement('a');
  enlace.href = URL.createObjectURL(blob);
  enlace.download = `${deporte}.json`;
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
}
```

Los registros antiguos no tienen usuario: los importados se asocian a la cuenta que los importa. Revisa los archivos antes de importar si el navegador era compartido.

## Verificación

La última verificación aprobó **45 pruebas**, incluidas las de navegador y la exportación a GitHub Pages. La prueba de MySQL real sigue omitida por falta de acceso al servidor. El detalle y sus límites están en `VERIFICACION.md`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas habituales usan dobles de la base: comprueban permisos, CSRF, escape HTML, cierre/rollback, hash, bloqueos, validación, duplicados/reglas de llaves y sesiones. **No demuestran por sí solas conectividad con tu MySQL remoto.**

Pruebas en Google Chrome instalado, a 320, 375, 768, 1024, 1440 y 1920 px:

```powershell
$env:RUN_BROWSER_TESTS="1"
.\.venv\Scripts\python.exe -m pytest tests/test_browser.py -q
```

Las capturas quedan en `test-results/` y utilizan datos ficticios exclusivamente en las pruebas. Se revisan login, dashboard y torneos, desbordamiento horizontal, búsqueda, menú, contraseña, cancelación de eliminación y logout. No se instala ni ejecuta una cuenta de demostración dentro de la aplicación real.

Para verificar PyMySQL y persistencia **real**, crea una segunda base **vacía y exclusiva de pruebas**, terminada en `_test`, y copia `.env.test.example` a `.env.test`. Configura sus credenciales y CA. Su usuario necesita los permisos de inicialización. La prueba se niega a usar `DB_NAME` de la aplicación y se niega a continuar si encuentra cuentas, inscripciones o partidos preexistentes. Crea las tablas/torneos y elimina únicamente los registros que ella crea.

```powershell
$env:RUN_MYSQL_TESTS="1"
.\.venv\Scripts\python.exe -m pytest tests/test_mysql_integration.py -q
```

La integración con el servidor remoto queda pendiente hasta que sea accesible y sus credenciales estén configuradas. El certificado sólo se configura si se utiliza TLS; es obligatorio para conexiones remotas en producción. No se ejecutaron migraciones ni se modificó ningún servidor remoto durante esta entrega.
