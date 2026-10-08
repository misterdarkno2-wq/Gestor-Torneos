# Verificación de la integración Supabase

Fecha: 8 de octubre de 2026 (hora de Chile).

**47 pruebas Python/navegador y 19 pruebas PostgreSQL aprobadas: 66 en total.**

Se aplicaron las migraciones `20261008023417_init_torneos_supabase`, `20261008023738_provision_invited_profiles` y `20261008030107_expand_sports_brackets` en el proyecto remoto, y sus versiones coinciden con los archivos locales. Hay ocho disciplinas iniciales, tablas con RLS y siete funciones públicas sin privilegios elevados. Se comprobó el servicio con la URL y clave publicable: `/auth/v1/settings` respondió HTTP 200 y `gt_state` rechazó el acceso anónimo. El usuario creó su cuenta Auth; se verificaron su correo confirmado y su perfil de profesor activo. No se copiaron registros de MySQL.

La aplicación Flask y el cliente GitHub Pages usan Supabase Auth y las mismas funciones PostgreSQL. Se retiró PyMySQL de las dependencias y la configuración local `.env` se actualizó. Sólo la URL y clave publicable se incluyen en el cliente; la exportación no lee `.env` ni permite claves administrativas.

Las 32 pruebas Python de rutas y adaptadores verifican CSRF, cookies HttpOnly/SameSite, protección de rutas, rol de estudiante, escape HTML, HTTPS verificado, timeout/cierre de respuestas, errores sanitizados, JWT por petición, sesiones privadas con identificadores aleatorios, renovación de refresh tokens, vencimiento local y cierre de sesión aun con fallos de red. Usan respuestas simuladas y un almacén temporal de sesiones.

Las 19 pruebas SQL ejecutan **las tres migraciones completas** en PostgreSQL mediante PGlite, con funciones y tablas Auth simuladas. Comprueban repetición de la migración inicial sin pérdida de datos, RLS/permisos, rechazo de acceso anónimo, cuentas sin perfil, escalamiento de rol, propiedad de inscripciones, normalización/duplicados, importación atómica, llaves del mismo torneo, ganador válido, avance a la final, invalidación al cambiar semifinal, bloqueo de eliminaciones y acceso con perfil inactivo o sesión revocada. También comprueban que el alta automática necesita autorización privada y correo confirmado, consume la autorización y no permite que estudiantes lean o creen invitaciones. La ampliación conserva los partidos y resultados existentes. Se comprueban las cuatro dimensiones de llaves, el avance hasta el campeón, la invalidación de todos los ancestros sin afectar otras ramas, la administración exclusiva del profesor, las inscripciones abiertas/cerradas, el vencimiento y la inclusión del último día en horario de Chile. No prueban un login real del proveedor.

Las 15 pruebas de navegador usan Chrome instalado. Siete comprueban Flask a 320, 375, 768, 1024, 1440 y 1920 px; ocho comprueban Pages bajo `/Gestor-Torneos/`, incluido 320, 768 y 1440 px. Verifican login, contraseña visible, datos cargados, registro, edición, confirmación/cancelación de eliminación, búsqueda, menú, logout, redirección por rol, escape de contenido dinámico, persistencia de sesión recordada, errores de login/esquema, importación y contratos RPC de llaves/resultados. Dos pruebas adicionales crean un torneo individual con plazo, importan 32 participantes, generan 31 partidos en cinco rondas y comprueban el cierre por fecha a 320 y 1440 px. Las respuestas de Supabase se interceptan exclusivamente en estas pruebas: no se escriben datos reales.

No hubo desbordamiento horizontal en las vistas comprobadas. Las capturas en `test-results/` usan datos de prueba; no son cuentas reales. Se comprobó también la sintaxis del JavaScript, compilación Python y construcción del SDK local.

La auditoría remota de seguridad señala dos observaciones:

- [RLS sin políticas en la tabla privada de invitaciones](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy): es intencional. No hay permisos de cliente y el acceso se deniega por defecto; sólo administración y el trigger autorizado consumen invitaciones.
- [Protección contra contraseñas filtradas desactivada](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection): la función requiere Pro o superior. No se activó ni se cambió la suscripción.

La auditoría de rendimiento informa de cuatro [índices todavía sin uso](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index), esperable antes de registrar equipos y partidos. Se conservan porque cubren claves foráneas y sus comprobaciones.

**Pendiente de comprobación por el usuario:** primer inicio de sesión con su contraseña, inscripción real y cierre de sesión en el sitio publicado. No se solicitó ni se conoce esa contraseña. El esquema y el perfil ya están preparados; las pruebas locales no sustituyen esta comprobación con una sesión real.
