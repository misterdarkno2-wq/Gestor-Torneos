-- Ampliación aditiva; conserva las llaves de cuatro y sus resultados.
begin;
alter table public.gt_tournaments drop constraint gt_tournaments_slug_check;
alter table public.gt_tournaments add constraint gt_tournaments_slug_check check (slug ~ '^[a-z][a-z0-9-]{1,59}$');
alter table public.gt_tournaments add column modalidad text not null default 'equipo' check (modalidad in ('equipo','individual'));
alter table public.gt_tournaments add column fecha_limite date;
alter table public.gt_tournaments add column inscripciones_abiertas boolean not null default true;
insert into public.gt_tournaments(slug,nombre,modalidad) values
 ('ajedrez','Ajedrez','individual'), ('tenis-mesa','Tenis de mesa','individual'),
 ('tenis','Tenis','individual'), ('badminton','Bádminton','individual'), ('balonmano','Balonmano','equipo')
 on conflict(slug) do nothing;

alter table public.gt_matches drop constraint gt_matches_fase_check;
alter table public.gt_matches add constraint gt_matches_fase_check
 check (fase in ('semifinal1','semifinal2','final') or fase ~ '^ronda[1-5]_[1-9][0-9]?$');
alter table public.gt_matches add column ronda integer;
alter table public.gt_matches add column posicion integer;
update public.gt_matches set ronda=case when fase='final' then 2 else 1 end,
 posicion=case when fase='semifinal2' then 2 else 1 end;
alter table public.gt_matches alter column ronda set not null;
alter table public.gt_matches alter column posicion set not null;
alter table public.gt_matches add constraint gt_match_round_check check (ronda between 1 and 5 and posicion between 1 and 16);
alter table public.gt_matches add constraint gt_match_round_position_key unique(torneo_id,ronda,posicion);

create or replace function gt_private.gt_registration_open(p_torneo bigint) returns void
language plpgsql set search_path='' as $$
begin
 if not exists(select 1 from public.gt_tournaments where id=p_torneo and inscripciones_abiertas
   and (fecha_limite is null or fecha_limite >= (now() at time zone 'America/Santiago')::date)) then
   raise sqlstate 'PT400' using message='Las inscripciones de este torneo están cerradas o su plazo venció.';
 end if;
end $$;

create or replace function gt_private.gt_bracket(p_torneo bigint,p_equipos bigint[]) returns void
language plpgsql security definer set search_path='' as $$
declare v_size integer; v_rounds integer; r integer; p integer; v_phase text;
begin
 perform gt_private.gt_lock(p_torneo,true);
 v_size := coalesce(cardinality(p_equipos),0);
 if v_size not in (4,8,16,32) or array_ndims(p_equipos) <> 1 or array_lower(p_equipos,1) <> 1
   or (select count(distinct x) from unnest(p_equipos) x) <> v_size then
   raise sqlstate 'PT400' using message='Selecciona 4, 8, 16 o 32 participantes distintos para las llaves.';
 end if;
 if (select count(*) from public.gt_registrations where torneo_id=p_torneo and id=any(p_equipos)) <> v_size then
   raise sqlstate 'PT400' using message='Todos los participantes deben pertenecer a este torneo.';
 end if;
 v_rounds := case v_size when 4 then 2 when 8 then 3 when 16 then 4 else 5 end;
 delete from public.gt_matches where torneo_id=p_torneo;
 for r in 1..v_rounds loop
   for p in 1..(v_size / (2^r)::integer) loop
     v_phase := case when r=v_rounds then 'final' when r=v_rounds-1 then 'semifinal'||p else 'ronda'||r||'_'||p end;
     insert into public.gt_matches(torneo_id,fase,ronda,posicion,equipo_a_id,equipo_b_id)
       values(p_torneo,v_phase,r,p,case when r=1 then p_equipos[2*p-1] end,case when r=1 then p_equipos[2*p] end);
   end loop;
 end loop;
end $$;

create or replace function gt_private.gt_winner(p_torneo bigint,p_partido bigint,p_ganador bigint) returns void
language plpgsql security definer set search_path='' as $$
declare v_match public.gt_matches; v_parent public.gt_matches; v_round integer; v_pos integer;
begin
 perform gt_private.gt_lock(p_torneo,true);
 select * into v_match from public.gt_matches where id=p_partido and torneo_id=p_torneo;
 if not found or v_match.equipo_a_id is null or v_match.equipo_b_id is null then
   raise sqlstate 'PT400' using message='El partido todavía no tiene dos participantes definidos.';
 end if;
 if p_ganador is null or p_ganador not in (v_match.equipo_a_id,v_match.equipo_b_id) then
   raise sqlstate 'PT400' using message='El ganador debe ser uno de los participantes de este partido.';
 end if;
 if v_match.ganador_id=p_ganador then return; end if;
 update public.gt_matches set ganador_id=p_ganador where id=p_partido;
 v_round := v_match.ronda; v_pos := v_match.posicion;
 -- Invalida sólo el camino dependiente; las otras ramas conservan sus resultados.
 loop
   select * into v_parent from public.gt_matches
     where torneo_id=p_torneo and ronda=v_round+1 and posicion=(v_pos+1)/2;
   exit when not found;
   update public.gt_matches set ganador_id=null,
     equipo_a_id=case when v_pos%2=1 then p_ganador else equipo_a_id end,
     equipo_b_id=case when v_pos%2=0 then p_ganador else equipo_b_id end
     where id=v_parent.id;
   v_round := v_parent.ronda; v_pos := v_parent.posicion; p_ganador := null;
 end loop;
end $$;

create or replace function gt_private.gt_manage_tournament(p_nombre text,p_slug text,p_modalidad text default 'equipo',
 p_fecha_limite date default null,p_abiertas boolean default true,p_id bigint default null) returns bigint
language plpgsql security definer set search_path='' as $$
declare v_id bigint; v_slug text;
begin
 if gt_private.gt_role()<>'profesor' then
   raise sqlstate 'PT403' using message='Esta acción requiere una cuenta de profesor.';
 end if;
 if p_slug is null or p_slug !~ '^[a-z][a-z0-9-]{1,59}$' or p_modalidad is null
   or p_modalidad not in ('equipo','individual') or p_abiertas is null then
   raise sqlstate 'PT400' using message='Revisa el identificador y la modalidad del torneo.';
 end if;
 if p_id is null then
   insert into public.gt_tournaments(nombre,slug,modalidad,fecha_limite,inscripciones_abiertas)
   values(gt_private.gt_clean(p_nombre,80),p_slug,p_modalidad,p_fecha_limite,p_abiertas) returning id into v_id;
 else
   perform gt_private.gt_lock(p_id,true);
   select slug into v_slug from public.gt_tournaments where id=p_id;
   if v_slug<>p_slug then raise sqlstate 'PT400' using message='El identificador de un torneo existente no puede cambiarse.'; end if;
   update public.gt_tournaments set nombre=gt_private.gt_clean(p_nombre,80),modalidad=p_modalidad,
     fecha_limite=p_fecha_limite,inscripciones_abiertas=p_abiertas where id=p_id returning id into v_id;
 end if;
 return v_id;
exception when unique_violation then
 raise sqlstate 'PT400' using message='Ya existe un torneo con ese identificador. Usa otro enlace.';
end $$;
revoke all on function gt_private.gt_manage_tournament(text,text,text,date,boolean,bigint) from public,anon,authenticated;
grant execute on function gt_private.gt_manage_tournament(text,text,text,date,boolean,bigint) to authenticated;
create or replace function public.gt_manage_tournament(p_nombre text,p_slug text,p_modalidad text default 'equipo',
 p_fecha_limite date default null,p_abiertas boolean default true,p_id bigint default null) returns bigint
language sql security invoker set search_path='' as $$
 select gt_private.gt_manage_tournament(p_nombre,p_slug,p_modalidad,p_fecha_limite,p_abiertas,p_id)
$$;
revoke all on function public.gt_manage_tournament(text,text,text,date,boolean,bigint) from public,anon,authenticated;
grant execute on function public.gt_manage_tournament(text,text,text,date,boolean,bigint) to authenticated;
revoke all on function gt_private.gt_registration_open(bigint) from public,anon,authenticated;
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
        select t.*, t.inscripciones_abiertas and (t.fecha_limite is null or t.fecha_limite >= (now() at time zone 'America/Santiago')::date) as inscripciones_disponibles,
          (select count(*) from public.gt_registrations i where i.torneo_id=t.id) as equipos,
          (select count(*) from public.gt_matches m where m.torneo_id=t.id and m.ganador_id is not null) as completados,
          (select count(*) from public.gt_matches m where m.torneo_id=t.id) as partidos
        from public.gt_tournaments t) x),
      'recent', (select coalesce(jsonb_agg(x order by x.id desc), '[]'::jsonb) from (
        select i.*, t.nombre as deporte, t.slug from public.gt_registrations i
        join public.gt_tournaments t on t.id=i.torneo_id
        where v_role='profesor' or i.usuario_id=auth.uid() order by i.id desc limit 6) x));
  end if;
  select * into v_t from public.gt_tournaments where slug=p_slug;
  if not found then raise sqlstate 'PT404' using message='No se encontró el torneo.'; end if;
  return v_result || jsonb_build_object('tournament', to_jsonb(v_t) || jsonb_build_object('inscripciones_disponibles',
    v_t.inscripciones_abiertas and (v_t.fecha_limite is null or v_t.fecha_limite >= (now() at time zone 'America/Santiago')::date)),
    'teams', (select coalesce(jsonb_agg(i order by i.id), '[]'::jsonb)
       from public.gt_registrations i where i.torneo_id=v_t.id),
    'matches', (select coalesce(jsonb_agg(x order by x.ronda,x.posicion), '[]'::jsonb) from (
      select m.*, a.nombre as equipo_a, b.nombre as equipo_b, g.nombre as ganador
      from public.gt_matches m left join public.gt_registrations a on a.id=m.equipo_a_id
      left join public.gt_registrations b on b.id=m.equipo_b_id
      left join public.gt_registrations g on g.id=m.ganador_id where m.torneo_id=v_t.id) x));
end $$;

create or replace function gt_private.gt_register(p_torneo bigint, p_nombre text, p_curso text)
returns bigint language plpgsql security definer set search_path = '' as $$
declare v_id bigint;
begin
  perform gt_private.gt_lock(p_torneo);
  perform gt_private.gt_registration_open(p_torneo);
  insert into public.gt_registrations(torneo_id, usuario_id, nombre, curso)
    values (p_torneo, auth.uid(), gt_private.gt_clean(p_nombre,60), gt_private.gt_clean(p_curso,20,true))
    returning id into v_id;
  return v_id;
end $$;

create or replace function gt_private.gt_import(p_torneo bigint, p_rows jsonb)
returns integer language plpgsql security definer set search_path = '' as $$
declare r jsonb; v_nombre text; v_curso text; v_count integer := 0; v_added integer;
begin
  perform gt_private.gt_lock(p_torneo);
  perform gt_private.gt_registration_open(p_torneo);
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


notify pgrst, 'reload schema';
commit;
