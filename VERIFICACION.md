# Verificación de la entrega

Fecha: 7 de octubre de 2026.

**Resultado: 40 pruebas aprobadas; 1 prueba de integración MySQL omitida.**

Se ejecutaron las pruebas de seguridad y reglas de negocio con dobles de conexión y datos simulados, y las pruebas de navegador en Google Chrome a 320, 375, 768, 1024, 1440 y 1920 píxeles. Las capturas en `test-results/` corresponden a datos ficticios, no a cuentas reales.

Se verificaron login con CSRF, mostrar/ocultar contraseña, cookie HttpOnly/SameSite, cierre y revocación de sesión, límites de acceso fallido, autorización por rol, propiedad de inscripciones, escape HTML, validación de entradas, cierre de cursores/conexiones, rollback y parametrización. Las reglas de las llaves comprueban la pertenencia de equipos y ganadores, y la actualización/invalidez de la final ante cambios de semifinal.

En navegador se comprobaron las vistas de login, dashboard y torneos, la búsqueda por deporte, el menú móvil, los controles de edición, la cancelación de eliminación y el logout de estudiante. No hay desbordamiento horizontal de página en los tamaños comprobados; las tablas tienen desplazamiento dentro de su contenedor. No se detectaron errores JavaScript ni violaciones de la política CSP en esas pruebas.

También se verificaron la compilación de Python y la sintaxis de JavaScript.

**Pendiente:** configurar las credenciales y la CA de tu MySQL remoto en `.env`, inicializar tablas y crear cuentas. No se comprobó una conexión real ni se ejecutaron consultas en tu servidor. `tests/test_mysql_integration.py` está preparado para comprobar persistencia y transacciones con PyMySQL real en una base separada y vacía, configurada mediante `.env.test`.

Las tablas no se crean al iniciar el servidor: requieren el comando `init-db` documentado en README. El login puede visualizarse sin conexión; iniciar sesión y gestionar torneos requieren MySQL disponible.
