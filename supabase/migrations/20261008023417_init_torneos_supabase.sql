-- Ejecutar completo en Supabase > SQL Editor. Es aditivo: no borra otras tablas.
begin;

create schema if not exists gt_private;
revoke all on schema gt_private from public, anon;
grant usage on schema gt_private to authenticated;

create table if not exists public.gt_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  nombre text not null check (char_length(nombre) between 2 and 80),
  rol text not null default 'estudiante' check (rol in ('profesor', 'estudiante')),
  activo boolean not null default true
);
create table if not exists public.gt_tournaments (
  id bigint generated always as identity primary key,
  slug text not null unique check (slug in ('futbol', 'basketball', 'voleibol')),
  nombre text not null
);
create table if not exists public.gt_registrations (
  id bigint generated always as identity primary key,
  torneo_id bigint not null references public.gt_tournaments(id),
  usuario_id uuid not null references public.gt_profiles(id),
  nombre text not null check (char_length(nombre) between 2 and 60),
  curso text not null check (char_length(curso) between 2 and 20),
  created_at timestamptz not null default now(),
  unique (id, torneo_id)
);
create unique index if not exists gt_registration_name_course
  on public.gt_registrations(torneo_id, lower(nombre), lower(curso));
create index if not exists gt_registration_owner on public.gt_registrations(usuario_id);
create table if not exists public.gt_matches (
  id bigint generated always as identity primary key,
  torneo_id bigint not null references public.gt_tournaments(id),
  fase text not null check (fase in ('semifinal1', 'semifinal2', 'final')),
  equipo_a_id bigint,
  equipo_b_id bigint,
  ganador_id bigint,
  unique (torneo_id, fase),
  foreign key (equipo_a_id, torneo_id) references public.gt_registrations(id, torneo_id),
  foreign key (equipo_b_id, torneo_id) references public.gt_registrations(id, torneo_id),
  foreign key (ganador_id, torneo_id) references public.gt_registrations(id, torneo_id),
  check (equipo_a_id is null or equipo_b_id is null or equipo_a_id <> equipo_b_id),
  check (ganador_id is null or (equipo_a_id is not null and equipo_b_id is not null
          and ganador_id in (equipo_a_id, equipo_b_id)))
);
create index if not exists gt_match_team_a on public.gt_matches(equipo_a_id,torneo_id);
create index if not exists gt_match_team_b on public.gt_matches(equipo_b_id,torneo_id);
create index if not exists gt_match_winner on public.gt_matches(ganador_id,torneo_id);
insert into public.gt_tournaments(slug, nombre) values
 ('futbol', 'Fútbol'), ('basketball', 'Básquetbol'), ('voleibol', 'Voleibol')
 on conflict (slug) do nothing;

-- El rol procede del perfil administrado, nunca de metadata editable del usuario.
create or replace function gt_private.gt_role() returns text
language plpgsql stable security definer set search_path = '' as $$
declare v_role text;
begin
  select p.rol into v_role from public.gt_profiles p
    where p.id = auth.uid() and p.activo;
  if v_role is null or not exists (
    select 1 from auth.sessions s where s.user_id = auth.uid()
    and s.id::text = auth.jwt()->>'session_id'
  ) then
    raise sqlstate 'PT403' using message = 'Tu cuenta no tiene acceso activo a Torneo. Contacta al administrador.';
  end if;
  return v_role;
end $$;

create or replace function gt_private.gt_clean(p_value text, p_max integer, p_course boolean default false)
returns text language plpgsql immutable set search_path = '' as $$
declare v text;
begin
  v := btrim(regexp_replace(normalize(p_value, NFC), '[[:space:]]+', ' ', 'g'));
  if v is null or char_length(v) not between 2 and p_max or
     v !~ (case when p_course then '^[[:alnum:] °-]+$' else '^[[:alnum:] ]+$' end) then
    raise sqlstate 'PT400' using message = 'Revisa nombre y curso: usa letras, números y espacios; el curso admite ° y guiones.';
  end if;
  return v;
end $$;

create or replace function gt_private.gt_state(p_slug text default null) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare v_role text; v_t public.gt_tournaments; v_result jsonb;
begin
  v_role := gt_private.gt_role();
  select jsonb_build_object('user', to_jsonb(p)) into v_result
    from public.gt_profiles p where p.id = auth.uid();
  if p_slug is null then
    return v_result || jsonb_build_object(
      'tournaments', (select coalesce(jsonb_agg(x order by x.id), '[]'::jsonb) from (
        select t.*, (select count(*) from public.gt_registrations i where i.torneo_id=t.id) as equipos,
          (select count(*) from public.gt_matches m where m.torneo_id=t.id and m.ganador_id is not null) as completados
        from public.gt_tournaments t) x),
      'recent', (select coalesce(jsonb_agg(x order by x.id desc), '[]'::jsonb) from (
        select i.*, t.nombre as deporte, t.slug from public.gt_registrations i
        join public.gt_tournaments t on t.id=i.torneo_id
        where v_role='profesor' or i.usuario_id=auth.uid() order by i.id desc limit 6) x));
  end if;
  select * into v_t from public.gt_tournaments where slug=p_slug;
  if not found then raise sqlstate 'PT404' using message='No se encontró el torneo.'; end if;
  return v_result || jsonb_build_object('tournament', to_jsonb(v_t),
    'teams', (select coalesce(jsonb_agg(i order by i.id), '[]'::jsonb)
       from public.gt_registrations i where i.torneo_id=v_t.id),
    'matches', (select coalesce(jsonb_agg(x order by x.fase), '[]'::jsonb) from (
      select m.*, a.nombre as equipo_a, b.nombre as equipo_b, g.nombre as ganador
      from public.gt_matches m left join public.gt_registrations a on a.id=m.equipo_a_id
      left join public.gt_registrations b on b.id=m.equipo_b_id
      left join public.gt_registrations g on g.id=m.ganador_id where m.torneo_id=v_t.id) x));
end $$;

create or replace function gt_private.gt_lock(p_torneo bigint, p_professor boolean default false)
returns void language plpgsql security definer set search_path = '' as $$
declare v_role text;
begin
  v_role := gt_private.gt_role();
  if p_professor and v_role <> 'profesor' then
    raise sqlstate 'PT403' using message='Esta acción requiere una cuenta de profesor.';
  end if;
  perform 1 from public.gt_tournaments where id=p_torneo for update;
  if not found then raise sqlstate 'PT404' using message='No se encontró el torneo.'; end if;
end $$;

create or replace function gt_private.gt_register(p_torneo bigint, p_nombre text, p_curso text)
returns bigint language plpgsql security definer set search_path = '' as $$
declare v_id bigint;
begin
  perform gt_private.gt_lock(p_torneo);
  insert into public.gt_registrations(torneo_id, usuario_id, nombre, curso)
    values (p_torneo, auth.uid(), gt_private.gt_clean(p_nombre,60), gt_private.gt_clean(p_curso,20,true))
    returning id into v_id;
  return v_id;
end $$;

create or replace function gt_private.gt_edit(p_torneo bigint, p_id bigint,
    p_nombre text default null, p_curso text default null, p_delete boolean default false)
returns void language plpgsql security definer set search_path = '' as $$
declare v_owner uuid;
begin
  perform gt_private.gt_lock(p_torneo);
  select usuario_id into v_owner from public.gt_registrations where id=p_id and torneo_id=p_torneo;
  if not found or (gt_private.gt_role() <> 'profesor' and v_owner <> auth.uid()) then
    raise sqlstate 'PT403' using message='No puedes modificar esta inscripción.';
  end if;
  if p_delete then
    if exists (select 1 from public.gt_matches where torneo_id=p_torneo
        and p_id in (equipo_a_id,equipo_b_id,ganador_id)) then
      raise sqlstate 'PT400' using message='El equipo está en las llaves. El profesor debe reorganizarlas antes de eliminarlo.';
    end if;
    delete from public.gt_registrations where id=p_id;
  else
    update public.gt_registrations set nombre=gt_private.gt_clean(p_nombre,60), curso=gt_private.gt_clean(p_curso,20,true) where id=p_id;
  end if;
end $$;

create or replace function gt_private.gt_bracket(p_torneo bigint, p_equipos bigint[])
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform gt_private.gt_lock(p_torneo, true);
  if coalesce(cardinality(p_equipos),0) <> 4 or (select count(distinct x) from unnest(p_equipos) x) <> 4 then
    raise sqlstate 'PT400' using message='Selecciona cuatro equipos distintos para las semifinales.';
  end if;
  if (select count(*) from public.gt_registrations where torneo_id=p_torneo and id=any(p_equipos)) <> 4 then
    raise sqlstate 'PT400' using message='Todos los equipos deben pertenecer a este torneo.';
  end if;
  delete from public.gt_matches where torneo_id=p_torneo;
  insert into public.gt_matches(torneo_id,fase,equipo_a_id,equipo_b_id) values
    (p_torneo,'semifinal1',p_equipos[1],p_equipos[2]),
    (p_torneo,'semifinal2',p_equipos[3],p_equipos[4]), (p_torneo,'final',null,null);
end $$;

create or replace function gt_private.gt_winner(p_torneo bigint, p_partido bigint, p_ganador bigint)
returns void language plpgsql security definer set search_path = '' as $$
declare v_match public.gt_matches; v_a bigint; v_b bigint;
begin
  perform gt_private.gt_lock(p_torneo, true);
  select * into v_match from public.gt_matches where id=p_partido and torneo_id=p_torneo;
  if not found or v_match.equipo_a_id is null or v_match.equipo_b_id is null then
    raise sqlstate 'PT400' using message='El partido todavía no tiene dos equipos definidos.';
  end if;
  if p_ganador is null or p_ganador not in (v_match.equipo_a_id,v_match.equipo_b_id) then
    raise sqlstate 'PT400' using message='El ganador debe ser uno de los equipos de este partido.';
  end if;
  if v_match.ganador_id = p_ganador then return; end if;
  update public.gt_matches set ganador_id=p_ganador where id=p_partido;
  if v_match.fase <> 'final' then
    select ganador_id into v_a from public.gt_matches where torneo_id=p_torneo and fase='semifinal1';
    select ganador_id into v_b from public.gt_matches where torneo_id=p_torneo and fase='semifinal2';
    update public.gt_matches set equipo_a_id=v_a, equipo_b_id=v_b, ganador_id=null
      where torneo_id=p_torneo and fase='final';
  end if;
end $$;

create or replace function gt_private.gt_import(p_torneo bigint, p_rows jsonb)
returns integer language plpgsql security definer set search_path = '' as $$
declare r jsonb; v_nombre text; v_curso text; v_count integer := 0; v_added integer;
begin
  perform gt_private.gt_lock(p_torneo);
  if p_rows is null or jsonb_typeof(p_rows) <> 'array' then
    raise sqlstate 'PT400' using message='El archivo debe contener una lista de inscripciones.';
  end if;
  if jsonb_array_length(p_rows) not between 1 and 100 or octet_length(p_rows::text)>131072 then
    raise sqlstate 'PT400' using message='El archivo admite entre 1 y 100 inscripciones y un máximo de 128 KB.';
  end if;
  for r in select value from jsonb_array_elements(p_rows) loop
    if jsonb_typeof(r->'nombre') is distinct from 'string' or jsonb_typeof(r->'curso') is distinct from 'string' then
      raise sqlstate 'PT400' using message='Cada inscripción necesita nombre y curso como texto.';
    end if;
    v_nombre := gt_private.gt_clean(r->>'nombre',60); v_curso := gt_private.gt_clean(r->>'curso',20,true);
    insert into public.gt_registrations(torneo_id,usuario_id,nombre,curso)
      values (p_torneo,auth.uid(),v_nombre,v_curso) on conflict do nothing;
    get diagnostics v_added = row_count; v_count := v_count+v_added;
  end loop;
  return v_count;
end $$;

alter table public.gt_profiles enable row level security;
alter table public.gt_tournaments enable row level security;
alter table public.gt_registrations enable row level security;
alter table public.gt_matches enable row level security;
revoke all on public.gt_profiles, public.gt_tournaments, public.gt_registrations, public.gt_matches from anon, authenticated;
grant select on public.gt_profiles, public.gt_tournaments, public.gt_registrations, public.gt_matches to authenticated;
grant all on public.gt_profiles to service_role;
drop policy if exists gt_profile_read on public.gt_profiles;
create policy gt_profile_read on public.gt_profiles for select to authenticated using (id=(select auth.uid()) and (select gt_private.gt_role()) is not null);
drop policy if exists gt_tournament_read on public.gt_tournaments;
create policy gt_tournament_read on public.gt_tournaments for select to authenticated using ((select gt_private.gt_role()) is not null);
drop policy if exists gt_registration_read on public.gt_registrations;
create policy gt_registration_read on public.gt_registrations for select to authenticated using ((select gt_private.gt_role()) is not null);
drop policy if exists gt_match_read on public.gt_matches;
create policy gt_match_read on public.gt_matches for select to authenticated using ((select gt_private.gt_role()) is not null);

-- Ninguna función se expone a anon. Los auxiliares sólo pueden usarse internamente.
revoke all on function gt_private.gt_role(), gt_private.gt_clean(text,integer,boolean), gt_private.gt_lock(bigint,boolean),
  gt_private.gt_state(text), gt_private.gt_register(bigint,text,text), gt_private.gt_edit(bigint,bigint,text,text,boolean),
  gt_private.gt_bracket(bigint,bigint[]), gt_private.gt_winner(bigint,bigint,bigint), gt_private.gt_import(bigint,jsonb)
  from public, anon, authenticated;
grant execute on function gt_private.gt_role(), gt_private.gt_state(text), gt_private.gt_register(bigint,text,text),
  gt_private.gt_edit(bigint,bigint,text,text,boolean), gt_private.gt_bracket(bigint,bigint[]),
  gt_private.gt_winner(bigint,bigint,bigint), gt_private.gt_import(bigint,jsonb) to authenticated;
-- API pública sin privilegios elevados: las implementaciones privadas verifican
-- identidad, perfil, sesión y permisos. El schema gt_private no se expone a REST.
create or replace function public.gt_state(p_slug text default null) returns jsonb
language sql stable security invoker set search_path = '' as $$ select gt_private.gt_state(p_slug) $$;
create or replace function public.gt_register(p_torneo bigint, p_nombre text, p_curso text) returns bigint
language sql security invoker set search_path = '' as $$ select gt_private.gt_register(p_torneo,p_nombre,p_curso) $$;
create or replace function public.gt_edit(p_torneo bigint,p_id bigint,p_nombre text default null,p_curso text default null,p_delete boolean default false) returns void
language sql security invoker set search_path = '' as $$ select gt_private.gt_edit(p_torneo,p_id,p_nombre,p_curso,p_delete) $$;
create or replace function public.gt_bracket(p_torneo bigint,p_equipos bigint[]) returns void
language sql security invoker set search_path = '' as $$ select gt_private.gt_bracket(p_torneo,p_equipos) $$;
create or replace function public.gt_winner(p_torneo bigint,p_partido bigint,p_ganador bigint) returns void
language sql security invoker set search_path = '' as $$ select gt_private.gt_winner(p_torneo,p_partido,p_ganador) $$;
create or replace function public.gt_import(p_torneo bigint,p_rows jsonb) returns integer
language sql security invoker set search_path = '' as $$ select gt_private.gt_import(p_torneo,p_rows) $$;
revoke all on function public.gt_state(text),public.gt_register(bigint,text,text),public.gt_edit(bigint,bigint,text,text,boolean),
 public.gt_bracket(bigint,bigint[]),public.gt_winner(bigint,bigint,bigint),public.gt_import(bigint,jsonb) from public,anon,authenticated;
grant execute on function public.gt_state(text),public.gt_register(bigint,text,text),public.gt_edit(bigint,bigint,text,text,boolean),
 public.gt_bracket(bigint,bigint[]),public.gt_winner(bigint,bigint,bigint),public.gt_import(bigint,jsonb) to authenticated;
notify pgrst, 'reload schema';
commit;
