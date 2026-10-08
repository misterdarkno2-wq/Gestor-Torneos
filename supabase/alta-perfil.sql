-- Primero crea la cuenta en Authentication > Users > Add user (correo y contraseña).
-- Cambia los tres valores. Ejecutar desde SQL Editor como administrador.
-- No tomamos el rol de user_metadata: el usuario podría editarlo.
insert into public.gt_profiles(id, nombre, rol)
select id, 'Nombre del profesor', 'profesor'
from auth.users where lower(email) = lower('REEMPLAZAR@ejemplo.cl')
on conflict (id) do update set nombre=excluded.nombre, rol=excluded.rol, activo=true;
-- Para un estudiante usa rol 'estudiante'. Si se insertan 0 filas, revisa el correo.
