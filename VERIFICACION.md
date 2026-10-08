# Verificación de la integración Supabase

Fecha: 7 de octubre de 2026 (hora de Chile).

**44 pruebas Python/navegador y 10 pruebas PostgreSQL aprobadas.**

Se comprobó el servicio remoto con la URL y clave publicable proporcionadas: `/auth/v1/settings` respondió HTTP 200. La función `gt_state` todavía devuelve `PGRST202`: **la migración no está instalada en el proyecto remoto**. No se crearon cuentas ni perfiles, ni se copiaron registros de MySQL.

La aplicación Flask y el cliente GitHub Pages usan Supabase Auth y las mismas funciones PostgreSQL. Se retiró PyMySQL de las dependencias y la configuración local `.env` se actualizó. Sólo la URL y clave publicable se incluyen en el cliente; la exportación no lee `.env` ni permite claves administrativas.

Las 31 pruebas Python de rutas y adaptadores verifican CSRF, cookies HttpOnly/SameSite, protección de rutas, rol de estudiante, escape HTML, HTTPS verificado, timeout/cierre de respuestas, errores sanitizados, JWT por petición, sesiones privadas con identificadores aleatorios, renovación de refresh tokens, vencimiento local y cierre de sesión aun con fallos de red. Usan respuestas simuladas y un almacén temporal de sesiones.

Las 10 pruebas SQL ejecutan **la migración completa** en PostgreSQL mediante PGlite, con funciones y tablas Auth simuladas. Comprueban migración repetible sin pérdida de datos, RLS/permisos, rechazo de acceso anónimo, cuentas sin perfil, escalamiento de rol, propiedad de inscripciones, normalización/duplicados, importación atómica, llaves del mismo torneo, ganador válido, avance a la final, invalidación al cambiar semifinal, bloqueo de eliminaciones y acceso con perfil inactivo o sesión revocada. No prueban el despliegue remoto del proveedor.

Las 13 pruebas de navegador usan Chrome instalado. Siete comprueban Flask a 320, 375, 768, 1024, 1440 y 1920 px; seis comprueban Pages bajo `/Gestor-Torneos/`, incluido 320, 768 y 1440 px. Verifican login, contraseña visible, datos cargados, registro, edición, confirmación/cancelación de eliminación, búsqueda, menú, logout, redirección por rol, escape de contenido dinámico, persistencia de sesión recordada, errores de login/esquema, importación y contratos RPC de llaves/resultados. Las respuestas de Supabase se interceptan exclusivamente en estas pruebas: no se escriben datos reales.

No hubo desbordamiento horizontal en las vistas comprobadas. Las capturas en `test-results/` usan datos de prueba; no son cuentas reales. Se comprobó también la sintaxis del JavaScript, compilación Python y construcción del SDK local.

**Pendiente para funcionar con datos reales:** instalar y conectar Supabase en Codex, aplicar `supabase/migrations/202610070001_torneos.sql`, crear cuentas Auth y sus perfiles, y verificar un login/inscripción reales. La clave publicable no otorga permisos administrativos. Las instrucciones están en `README.md` y la migración también puede ejecutarse completa en el SQL Editor del proyecto.
