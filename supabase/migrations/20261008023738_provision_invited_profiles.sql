begin;
-- Altas autorizadas sólo por administración. Sin endpoints para asignar roles.
create table gt_private.gt_invited_profiles (
  email text primary key check (email=lower(btrim(email))),
  nombre text not null check (char_length(nombre) between 2 and 80),
  rol text not null check (rol in ('profesor','estudiante'))
);
alter table gt_private.gt_invited_profiles enable row level security;
revoke all on gt_private.gt_invited_profiles from public,anon,authenticated;

create function gt_private.gt_provision_invited_profile() returns trigger
language plpgsql security definer set search_path='' as $$
declare invitation gt_private.gt_invited_profiles;
begin
  -- El correo ha de estar verificado. Metadata editable nunca determina el rol.
  if new.email_confirmed_at is null or new.email is null then return new; end if;
  select * into invitation from gt_private.gt_invited_profiles
    where email=lower(btrim(new.email)) for update;
  if not found then return new; end if;
  insert into public.gt_profiles(id,nombre,rol,activo)
    values(new.id,invitation.nombre,invitation.rol,true)
    on conflict(id) do update set nombre=excluded.nombre,rol=excluded.rol,activo=true;
  delete from gt_private.gt_invited_profiles where email=invitation.email;
  return new;
end $$;
revoke all on function gt_private.gt_provision_invited_profile() from public,anon,authenticated,service_role;
create trigger gt_auth_provision_invited_profile
after insert or update of email,email_confirmed_at on auth.users
for each row execute function gt_private.gt_provision_invited_profile();
commit;
