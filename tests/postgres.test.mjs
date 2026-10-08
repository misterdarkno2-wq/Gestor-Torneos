import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { test, after } from 'node:test';

const db = new PGlite();
after(() => db.close());
const sql = await readFile(new URL('../supabase/migrations/20261008023417_init_torneos_supabase.sql', import.meta.url), 'utf8');
const professor = '10000000-0000-4000-8000-000000000001';
const student = '10000000-0000-4000-8000-000000000002';
const outsider = '10000000-0000-4000-8000-000000000003';
await db.exec(`
  create role anon; create role authenticated; create role service_role bypassrls;
  create schema auth; grant usage on schema auth, public to anon, authenticated, service_role;
  create table auth.users(id uuid primary key, email text);
  create table auth.sessions(id uuid primary key, user_id uuid references auth.users(id));
  create function auth.jwt() returns jsonb language sql stable as $$select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb$$;
  create function auth.uid() returns uuid language sql stable as $$select (auth.jwt()->>'sub')::uuid$$;
  insert into auth.users values ('${professor}','profesor@example.test'), ('${student}','estudiante@example.test'), ('${outsider}','otro@example.test');
  insert into auth.sessions select id,id from auth.users;
`);
await db.exec(sql);
await db.query('insert into public.gt_profiles(id,nombre,rol) values ($1,$2,$3),($4,$5,$6)', [professor,'Profesora Prueba','profesor',student,'Estudiante Prueba','estudiante']);
const tournaments = (await db.query('select * from public.gt_tournaments order by id')).rows;
const tid = tournaments[0].id, other = tournaments[1].id;
async function identity(id, role = 'authenticated') {
  await db.exec('reset role');
  await db.query("select set_config('request.jwt.claims',$1,false)", [JSON.stringify(id ? {sub:id,session_id:id} : {})]);
  await db.exec(`set role ${role}`);
}
async function call(name, params) {
  return (await db.query(`select public.${name}(${params.map((_,i)=>`$${i+1}`).join(',')}) as value`, params)).rows[0].value;
}
async function rejects(fn, code) { await assert.rejects(fn, error => error.code === code); }
let teams;

test('La migración es repetible y conserva datos existentes', async () => {
  await db.exec('reset role'); await db.exec(sql);
  assert.equal((await db.query('select count(*)::int n from public.gt_profiles')).rows[0].n, 2);
});
test('Anon no puede leer tablas ni ejecutar funciones', async () => {
  await identity(null,'anon');
  await rejects(()=>call('gt_state',[null]),'42501');
  await rejects(()=>db.query('select * from public.gt_registrations'),'42501');
});
test('Una cuenta Auth sin perfil no obtiene acceso', async () => {
  await identity(outsider); await rejects(()=>call('gt_state',[null]),'PT403');
});
test('Alumno no puede elevar rol ni escribir tablas directamente', async () => {
  await identity(student);
  await rejects(()=>db.query("update public.gt_profiles set rol='profesor'"),'42501');
  await rejects(()=>db.query("insert into public.gt_registrations(torneo_id,usuario_id,nombre,curso) values ($1,$2,'Intruso','3 A')",[tid,professor]),'42501');
  await rejects(()=>db.query('select gt_private.gt_lock($1,true)',[tid]),'42501');
});
test('Inscripción validada, identidad del JWT y duplicados normalizados', async () => {
  await identity(student);
  const id = await call('gt_register',[tid,'Los Cóndores','3° Medio A']);
  const state = await call('gt_state',['futbol']);
  assert.equal(state.teams[0].usuario_id,student); assert.equal(state.teams[0].id,id);
  await rejects(()=>call('gt_register',[tid,'los cóndores','3° medio a']),'23505');
  await rejects(()=>call('gt_register',[tid,'<script>','3 A']),'PT400');
  assert.equal(state.user.rol,'estudiante');
  teams=[id];
});
test('Alumno sólo edita sus propias inscripciones; profesor puede administrarlas', async () => {
  await identity(professor);
  teams.push(await call('gt_register',[tid,'Otro Equipo','4 A']));
  await identity(student);
  await rejects(()=>call('gt_edit',[tid,teams[1],'Cambio','3 A',false]),'PT403');
  await rejects(()=>call('gt_edit',[tid,teams[1],null,null,true]),'PT403');
  await call('gt_edit',[tid,teams[0],'Los Cóndores','3° Medio B',false]);
  await identity(professor); await call('gt_edit',[tid,teams[0],'Los Cóndores','3° Medio A',false]);
});
test('Importar es atómico y omite duplicados', async () => {
  await identity(student);
  const before = (await call('gt_state',['futbol'])).teams.length;
  await rejects(()=>call('gt_import',[tid,JSON.stringify([{nombre:'Equipo Nuevo',curso:'3 A'},{nombre:'<script>',curso:'3 A'}])]),'PT400');
  assert.equal((await call('gt_state',['futbol'])).teams.length,before);
  assert.equal(await call('gt_import',[tid,JSON.stringify([{nombre:'Los Cóndores',curso:'3° Medio A'},{nombre:'Equipo Tercero',curso:'3 A'}])]),1);
  await rejects(()=>call('gt_import',[tid,JSON.stringify([{nombre:42,curso:'3 A'}])]),'PT400');
  await identity(professor); teams=(await call('gt_state',['futbol'])).teams.map(t=>t.id);
  teams.push(await call('gt_register',[tid,'Equipo Cuarto','3 A']));
});
test('Sólo profesor crea llaves; valida cuatro equipos del mismo torneo', async () => {
  await identity(student); await rejects(()=>call('gt_bracket',[tid,teams]),'PT403');
  await identity(professor);
  const foreign = await call('gt_register',[other,'Equipo Ajeno','3 A']);
  await rejects(()=>call('gt_bracket',[tid,[...teams.slice(0,3),foreign]]),'PT400');
  await rejects(()=>call('gt_bracket',[tid,[teams[0],teams[0],teams[1],teams[2]]]),'PT400');
  await call('gt_bracket',[tid,teams]); assert.equal((await call('gt_state',['futbol'])).matches.length,3);
});
test('Resultados, final automática, cambio de semifinal y eliminación protegida', async () => {
  await identity(professor);
  const matches = (await call('gt_state',['futbol'])).matches;
  const a = matches.find(m=>m.fase==='semifinal1'), b=matches.find(m=>m.fase==='semifinal2'), f=matches.find(m=>m.fase==='final');
  await identity(student); await rejects(()=>call('gt_winner',[tid,a.id,teams[0]]),'PT403');
  await identity(professor); await rejects(()=>call('gt_winner',[tid,a.id,teams[2]]),'PT400');
  await rejects(()=>call('gt_winner',[tid,f.id,teams[0]]),'PT400');
  await call('gt_winner',[tid,a.id,teams[0]]); await call('gt_winner',[tid,b.id,teams[2]]);
  await call('gt_winner',[tid,f.id,teams[0]]);
  await call('gt_winner',[tid,a.id,teams[0]]); // Igual ganador conserva final.
  assert.equal((await call('gt_state',['futbol'])).matches.find(m=>m.id===f.id).ganador_id,teams[0]);
  await call('gt_winner',[tid,a.id,teams[1]]);
  const final = (await call('gt_state',['futbol'])).matches.find(m=>m.id===f.id);
  assert.equal(final.equipo_a_id,teams[1]); assert.equal(final.equipo_b_id,teams[2]); assert.equal(final.ganador_id,null);
  await rejects(()=>call('gt_edit',[tid,teams[0],null,null,true]),'PT400');
});
test('Perfil desactivado y sesión revocada cortan acceso a la base', async () => {
  await db.exec('reset role'); await db.query('update public.gt_profiles set activo=false where id=$1',[student]);
  await identity(student); await rejects(()=>call('gt_state',[null]),'PT403');
  await db.exec('reset role'); await db.query('update public.gt_profiles set activo=true where id=$1',[student]);
  await db.query('delete from auth.sessions where user_id=$1',[student]);
  await identity(student); await rejects(()=>call('gt_register',[tid,'Otra Prueba','3 A']),'PT403');
});

test('Alta de perfiles sólo por invitación administrativa y correo verificado', async () => {
  await db.exec('reset role');
  await db.exec('alter table auth.users add column email_confirmed_at timestamptz');
  const files = await import('node:fs/promises');
  const names = await files.readdir(new URL('../supabase/migrations/', import.meta.url));
  const invitationSQL = await readFile(new URL('../supabase/migrations/'+names.find(n=>n.endsWith('_provision_invited_profiles.sql')), import.meta.url), 'utf8');
  await db.exec(invitationSQL);
  const invited='20000000-0000-4000-8000-000000000001';
  const uninvited='20000000-0000-4000-8000-000000000002';
  await db.query("insert into gt_private.gt_invited_profiles values ('admin@example.test','Administrador','profesor')");
  await db.query('insert into auth.users(id,email) values ($1,$2)',[invited,'admin@example.test']);
  assert.equal((await db.query('select count(*)::int n from public.gt_profiles where id=$1',[invited])).rows[0].n,0);
  await db.query('update auth.users set email_confirmed_at=now() where id=$1',[invited]);
  assert.equal((await db.query('select rol from public.gt_profiles where id=$1',[invited])).rows[0].rol,'profesor');
  assert.equal((await db.query('select count(*)::int n from gt_private.gt_invited_profiles')).rows[0].n,0);
  await db.query('insert into auth.users(id,email,email_confirmed_at) values ($1,$2,now())',[uninvited,'other@example.test']);
  assert.equal((await db.query('select count(*)::int n from public.gt_profiles where id=$1',[uninvited])).rows[0].n,0);
  await identity(student);
  await rejects(()=>db.query('select * from gt_private.gt_invited_profiles'),'42501');
  await rejects(()=>db.query("insert into gt_private.gt_invited_profiles values ('intruder@example.test','Intruso','profesor')"),'42501');
});
