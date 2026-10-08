import { createClient } from '@supabase/supabase-js';
import config from '../supabase/public-config.json';
import sports from '../app/data/sports.json';

const root = document.body;
if (root.hasAttribute('data-pages-live')) start();

async function start() {
  const status = document.getElementById('connection-status');
  const content = document.getElementById('page-content');
  const expectedRole = root.dataset.role;
  const slug = root.dataset.slug === 'torneo' ? new URLSearchParams(location.search).get('torneo') : root.dataset.slug;
  const prefix = `torneo-${new URL(config.url).hostname}`;
  const preference = `${prefix}-remember`;
  const storage = {
    getItem: key => sessionStorage.getItem(key) ?? localStorage.getItem(key),
    setItem: (key, value) => {
      const remembered = localStorage.getItem(preference) === 'yes';
      (remembered ? sessionStorage : localStorage).removeItem(key);
      (remembered ? localStorage : sessionStorage).setItem(key, value);
    },
    removeItem: key => { sessionStorage.removeItem(key); localStorage.removeItem(key); }
  };
  const client = createClient(config.url, config.publishableKey, {
    auth: { storage, storageKey: `${prefix}-auth`, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
    global: { fetch: (url, options = {}) => fetch(url, {
      ...options, signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000)
    }) }
  });
  let user, tournament;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const date = value => new Date(value).toLocaleDateString('es-CL', {timeZone: 'UTC'});
  const target = (role, sport = '') => sport ? (Object.hasOwn(sports,sport) ? `${role}-${sport}.html` : `${role}-torneo.html?torneo=${encodeURIComponent(sport)}`) : `dashboard-${role}.html`;
  if (root.dataset.slug === 'torneo' && (!slug || !/^[a-z][a-z0-9-]{1,59}$/.test(slug))) {
    location.replace(target(expectedRole)); return;
  }

  const icons = new Map([...document.querySelectorAll('#tournament-nav a')].map(a => [a.getAttribute('href').split('-').slice(1).join('-').replace('.html',''), a.querySelector('svg')?.outerHTML || '']));
  const fallbackIcon = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M8 3h8v6a4 4 0 0 1-8 0zM8 5H4v3a4 4 0 0 0 4 4m8-7h4v3a4 4 0 0 1-4 4M12 13v5m-4 3h8"/></svg>';
  const sportInfo = t => ({icon:'trophy',color:'purple',description:'Una nueva competencia para tu comunidad.',...sports[t.slug],label:t.nombre,individual:t.modalidad === 'individual'});
  const today = () => new Intl.DateTimeFormat('en-CA',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const closed = t => t.inscripciones_disponibles === false || t.inscripciones_abiertas === false || Boolean(t.fecha_limite && t.fecha_limite < today());
  function renderNav(tournaments) {
    const nav = document.getElementById('tournament-nav');
    nav.innerHTML = `<a class="nav-item ${slug ? '' : 'active'}" href="${target(user.rol)}">${fallbackIcon} Resumen</a><p class="nav-label">TORNEOS</p>${tournaments.map(t => `<a class="nav-item ${slug === t.slug ? 'active' : ''}" ${slug === t.slug ? 'aria-current="page"' : ''} href="${escape(target(user.rol,t.slug))}">${icons.get(t.slug)||fallbackIcon} ${escape(t.nombre)}</a>`).join('')}`;
  }
  function configureAdmin(t) {
    const form = document.querySelector('.tournament-admin-form');
    if (!form) return;
    form.elements.torneo_id.value = t?.id || '';
    form.elements.nombre.value = t?.nombre || '';
    form.elements.slug.value = t?.slug || '';
    form.elements.slug.readOnly = Boolean(t);
    form.elements.modalidad.value = t?.modalidad || 'equipo';
    form.elements.fecha_limite.value = t?.fecha_limite || '';
    form.elements.abiertas.checked = t?.inscripciones_abiertas !== false;
    form.querySelector('button[type=submit]').textContent = t ? 'Guardar torneo' : 'Crear torneo';
  }

  function message(error) {
    if (error.code === '23505') return 'Ya existe una inscripción con ese nombre y curso en este torneo.';
    if (['PT400', 'PT403', 'PT404'].includes(error.code)) return error.message;
    if (error.code === 'PGRST202' || error.code === '42P01') return 'Falta preparar las tablas de Torneo en Supabase. Contacta al administrador.';
    if (error.status === 429) return 'Demasiados intentos. Espera unos minutos antes de volver a intentar.';
    if (error.code === 'email_not_confirmed') return 'Confirma tu correo antes de iniciar sesión.';
    if (['invalid_credentials', 'invalid_grant'].includes(error.code)) return 'Correo o contraseña incorrectos.';
    if (error.status === 401 || error.code === 'PGRST301') return 'Tu sesión venció. Cierra sesión e ingresa nuevamente.';
    return 'No pudimos completar la operación. Revisa tu conexión e inténtalo nuevamente.';
  }

  function toast(text, type = 'success') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.setAttribute('role', 'status');
    const span = document.createElement('span');
    span.textContent = text;
    const close = document.createElement('button');
    close.type = 'button'; close.className = 'icon-button toast-close'; close.textContent = '×';
    close.setAttribute('aria-label', 'Cerrar aviso');
    el.append(span, close);
    document.querySelector('.toast-region').append(el);
  }

  async function rpc(name, params = {}) {
    const { data, error } = await client.rpc(name, params);
    if (error) throw error;
    return data;
  }

  async function logout() {
    const { error } = await client.auth.signOut({scope: 'local'});
    if (error) {
      // También corta el acceso local si no hay red; la sesión remota puede seguir activa.
      await client.auth.signOut({scope: 'local'}).catch(() => {});
      storage.removeItem(`${prefix}-auth`);
      sessionStorage.setItem('gt-flash', 'Se cerró el acceso en este navegador. No se pudo confirmar el cierre remoto; inténtalo al recuperar la conexión.');
    }
    localStorage.removeItem(preference);
    location.replace('index.html');
  }

  function fillProfile() {
    document.querySelector('.sidebar-profile strong').textContent = user.nombre;
    document.querySelector('.sidebar-profile small').textContent = user.rol;
    document.querySelector('.profile-name').textContent = user.nombre;
    document.querySelector('.topbar .role-badge').textContent = user.rol;
    document.querySelectorAll('.sidebar-profile .avatar, .topbar .avatar').forEach(el => { el.textContent = user.nombre.slice(0, 1).toUpperCase(); });
    document.querySelectorAll('form[action="index.html"]').forEach(form => { form.dataset.operation = 'logout'; });
  }

  function renderDashboard(data) {
    const tournaments = data.tournaments;
    document.querySelector('.page-heading h1').textContent = `Hola, ${user.nombre.split(' ')[0]}`;
    const stats = [tournaments.length, tournaments.reduce((n, t) => n + t.equipos, 0), tournaments.reduce((n, t) => n + t.completados, 0)];
    document.querySelectorAll('.stat-card strong').forEach((el, i) => { el.textContent = stats[i]; });
    document.querySelector('.tournament-grid').innerHTML = tournaments.map(t => {
      const sport = sportInfo(t);
      return `<article class="tournament-card" data-search="${escape(t.nombre)} ${escape(t.slug)}"><div class="sport-art ${sport.color}"><span class="sport-ball">${icons.get(t.slug)||fallbackIcon}</span><span class="sport-number">${sport.individual ? 'INDIVIDUAL' : 'EQUIPOS'}</span></div><div class="tournament-card-content"><div class="card-title"><h3>${escape(t.nombre)}</h3><span class="status-pill ${closed(t) ? 'pending' : ''}">${closed(t) ? 'Cerrado' : 'Disponible'}</span></div><p>${escape(sport.description)}</p><div class="card-meta"><span>${t.equipos} participantes</span><span>${t.completados}/${t.partidos || 0} resultados</span></div>${t.fecha_limite ? `<p>Inscripciones hasta ${escape(t.fecha_limite)}</p>` : ''}<a class="card-link" href="${escape(target(user.rol,t.slug))}">${user.rol === 'profesor' ? 'Gestionar torneo' : 'Ver torneo'} →</a></div></article>`;
    }).join('');
    document.getElementById('tournament-search').dispatchEvent(new Event('input'));
    configureAdmin(null);
    const recent = document.querySelector('.recent-panel');
    const old = recent.querySelector('.empty-state, .table-wrap');
    old?.remove();
    recent.insertAdjacentHTML('beforeend', data.recent.length ? `<div class="table-wrap" role="region" aria-label="Últimas inscripciones" tabindex="0"><table><thead><tr><th>Equipo / participante</th><th>Disciplina</th><th>Curso</th><th>Inscripción (UTC)</th><th>Acción</th></tr></thead><tbody>${data.recent.map(r => `<tr><td><strong>${escape(r.nombre)}</strong></td><td>${escape(r.deporte)}</td><td>${escape(r.curso)}</td><td>${escape(date(r.created_at))}</td><td><a class="text-link" href="${escape(target(user.rol, r.slug))}#equipos">Ver →</a></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty-state"><h3>Aquí comienza tu próximo equipo</h3><p>Las inscripciones aparecerán aquí cuando se registren.</p></div>');
  }

  function renderTournament(data) {
    tournament = data.tournament;
    const teams = data.teams, matches = data.matches;
    document.querySelector('.page-heading .role-badge').textContent = `${teams.length} equipos inscritos`;
    document.querySelector('.count-badge').textContent = teams.length;
    document.querySelector('.registration-panel form').dataset.operation = 'register';
    document.querySelector('.import-details form').dataset.operation = 'import';
    const panel = document.querySelector('.teams-panel');
    panel.querySelector('.team-list, .empty-state')?.remove();
    panel.insertAdjacentHTML('beforeend', teams.length ? `<div class="team-list">${teams.map(t => {
      const own = t.usuario_id === user.id, editable = own || user.rol === 'profesor';
      return `<article class="team-row"><span class="team-avatar">${escape(t.nombre.slice(0,2).toUpperCase())}</span><div class="team-info"><h3>${escape(t.nombre)}</h3><p>${escape(t.curso)}${own ? '<span class="own-tag">Tu inscripción</span>' : ''}</p></div>${editable ? `<div class="team-actions"><button type="button" class="icon-button" data-edit="edit-${t.id}" aria-label="Editar ${escape(t.nombre)}" aria-expanded="false" aria-controls="edit-${t.id}">✎</button><form method="post" data-operation="delete" data-id="${t.id}" data-confirm="¿Eliminar la inscripción de ${escape(t.nombre)}? Esta acción no se puede deshacer."><button type="submit" class="icon-button danger-text" aria-label="Eliminar ${escape(t.nombre)}">×</button></form></div><form class="edit-team form-stack" id="edit-${t.id}" hidden method="post" data-operation="edit" data-id="${t.id}"><label for="name-${t.id}">Nombre</label><input id="name-${t.id}" name="nombre" value="${escape(t.nombre)}" minlength="2" maxlength="60" required><label for="course-${t.id}">Curso</label><input id="course-${t.id}" name="curso" value="${escape(t.curso)}" minlength="2" maxlength="20" required><button class="button primary" type="submit">Guardar cambios</button></form>` : ''}</article>`;
    }).join('')}</div>` : '<div class="empty-state"><h3>La cancha espera a su primer equipo</h3><p>Completa el formulario para comenzar.</p></div>');
    const bracket = document.querySelector('.bracket-panel');
    bracket.querySelectorAll('.bracket-grid, .bracket-rounds, .empty-state, .bracket-settings').forEach(el => el.remove());
    bracket.insertAdjacentHTML('beforeend', renderBracket(matches));
    if (user.rol === 'profesor') bracket.insertAdjacentHTML('beforeend', `<details class="bracket-settings" ${matches.length ? '' : 'open'}><summary>${matches.length ? 'Reorganizar llaves' : 'Organizar llaves'}</summary><p class="muted">Se enfrentan en el orden de la lista: 1 vs 2, 3 vs 4, etc. Las siguientes rondas se completan con los ganadores.</p>${teams.length >= 4 ? `<form class="form-stack" method="post" data-operation="bracket" ${matches.length ? 'data-confirm="¿Reorganizar las llaves? Se borrarán los partidos y resultados actuales de este torneo."' : ''}><label for="bracket-size">Tamaño de las llaves</label><select id="bracket-size" name="tamano">${[4,8,16,32].map(n=>`<option value="${n}" ${n === matches.length+1 ? 'selected' : ''} ${n>teams.length ? 'disabled' : ''}>${n} participantes · ${n-1} partidos${n>teams.length ? ' (faltan inscripciones)' : ''}</option>`).join('')}</select><p class="selection-count muted" aria-live="polite">0 participantes seleccionados</p><fieldset class="team-select"><legend>Participantes de las llaves</legend>${teams.map(t => `<label class="checkbox-label"><input type="checkbox" name="equipos" value="${t.id}"> ${escape(t.nombre)} <small>${escape(t.curso)}</small></label>`).join('')}</fieldset><button type="submit" class="button primary">Guardar llaves</button></form>` : `<div class="inline-note">Faltan ${4-teams.length} participantes para organizar las llaves.</div>`}</details>`);
    const sport = sportInfo(tournament);
    document.title = `${tournament.nombre} · Torneo`;
    document.querySelector('.page-heading h1').innerHTML = `<span class="title-sport ${sport.color}">${icons.get(tournament.slug)||fallbackIcon}</span>${escape(tournament.nombre)}`;
    document.querySelector('.breadcrumb strong').textContent = tournament.nombre;
    configureAdmin(tournament);
    document.querySelector('.registration-panel > h2').textContent = sport.individual ? 'Inscribe un participante' : 'Suma tu equipo';
    document.getElementById('nombre').placeholder = sport.individual ? 'Ej. Sofía Pérez' : 'Ej. Los Cóndores';
    document.querySelector('.registration-status')?.remove();
    document.querySelector('.registration-panel form').insertAdjacentHTML('beforebegin', `<p class="registration-status">${closed(tournament) ? 'Inscripciones cerradas.' : 'Inscripciones abiertas.'}${tournament.fecha_limite ? ` Hasta el ${escape(tournament.fecha_limite)} (horario de Chile).` : ''}</p>`);
    document.querySelectorAll('[data-operation="register"], [data-operation="import"]').forEach(form=>form.querySelectorAll('input,button').forEach(el=>{el.disabled=closed(tournament);}));
  }

  function renderBracket(matches) {
    if (!matches.length) return '<div class="empty-state"><h3>El camino a la final está por comenzar</h3><p>Elige llaves de 4, 8, 16 o 32 participantes.</p></div>';
    const rounds = new Map();
    for (const m of matches) {
      const r=m.ronda || (m.fase === 'final' ? 2 : 1);
      const p=m.posicion || (m.fase === 'semifinal2' ? 2 : 1);
      if (!rounds.has(r)) rounds.set(r,[]);
      rounds.get(r).push({...m,ronda:r,posicion:p});
    }
    const last=Math.max(...rounds.keys()), names=['Final','Semifinales','Cuartos de final','Octavos de final','Dieciseisavos de final'];
    return `<div class="bracket-rounds" role="region" aria-label="Rondas del torneo" tabindex="0">${[...rounds].sort(([a],[b])=>a-b).map(([r,items])=>`<details class="bracket-round" open><summary>${names[last-r]} <span class="muted">${items.length} ${items.length===1 ? 'partido' : 'partidos'}</span></summary><div class="round-matches">${items.sort((a,b)=>a.posicion-b.posicion).map(m=>`<article class="match-card ${m.fase === 'final' ? 'final-match' : ''}"><div class="match-heading"><span>${m.fase === 'final' ? 'Final' : `Partido ${m.posicion}`}</span><span class="status-pill ${m.ganador_id ? '' : 'pending'}">${m.ganador_id ? 'Resuelto' : 'Pendiente'}</span></div><div class="match-team ${m.ganador_id === m.equipo_a_id && m.ganador_id ? 'winner' : ''}"><span>${escape(m.equipo_a || `Ganador del partido ${m.posicion*2-1} de la ronda anterior`)}</span></div><div class="match-versus">VS</div><div class="match-team ${m.ganador_id === m.equipo_b_id && m.ganador_id ? 'winner' : ''}"><span>${escape(m.equipo_b || `Ganador del partido ${m.posicion*2} de la ronda anterior`)}</span></div>${user.rol === 'profesor' && m.equipo_a_id && m.equipo_b_id ? `<form class="result-form form-stack" method="post" data-operation="winner" data-id="${m.id}" ${m.ganador_id ? 'data-confirm="¿Cambiar el ganador? Se borrarán los resultados posteriores que dependan de este partido."' : ''}><label for="winner-${m.id}">Participante ganador</label><select id="winner-${m.id}" name="ganador" required><option value="">Selecciona el ganador</option>${[[m.equipo_a_id,m.equipo_a],[m.equipo_b_id,m.equipo_b]].map(([id,name])=>`<option value="${id}" ${m.ganador_id===id ? 'selected' : ''}>${escape(name)}</option>`).join('')}</select><button class="button secondary" type="submit">Guardar resultado</button></form>` : m.ganador ? `<p class="winner-label">Ganador: ${escape(m.ganador)}</p>` : ''}</article>`).join('')}</div></details>`).join('')}</div>`;
  }

  async function refresh() {
    const data = await rpc('gt_state', {p_slug: slug || null});
    user = data.user;
    if (user.rol !== expectedRole) { location.replace(target(user.rol, slug)); return; }
    fillProfile();
    const overview = slug ? await rpc('gt_state',{p_slug:null}) : data;
    renderNav(overview.tournaments);
    slug ? renderTournament(data) : renderDashboard(data);
    content.hidden = false; status.hidden = true;
  }

  function reset(form) {
    form.classList.remove('loading'); form.removeAttribute('aria-busy'); delete form.dataset.confirmed;
    form.querySelectorAll('button[type=submit]').forEach(button => { button.disabled = Boolean(tournament && ['register','import'].includes(form.dataset.operation) && closed(tournament)); });
  }

  document.addEventListener('submit', async event => {
    if (event.defaultPrevented) return; // La confirmación del usuario sigue pendiente.
    event.preventDefault();
    const form = event.target, fields = new FormData(form), operation = form.dataset.operation;
    try {
      if (form.id === 'loginForm') {
        const remembered = fields.get('recordar') === 'on';
        if (remembered) localStorage.setItem(preference, 'yes'); else localStorage.removeItem(preference);
        document.querySelector('#login-error')?.remove();
        const {error} = await client.auth.signInWithPassword({email: fields.get('usuario').trim().toLowerCase(), password: fields.get('contrasena')});
        if (error) throw error;
        let data;
        try { data = await rpc('gt_state', {p_slug: null}); }
        catch (error) { await client.auth.signOut({scope:'local'}); throw error; }
        location.assign(target(data.user.rol));
        return;
      }
      if (operation === 'logout') { await logout(); return; }
      if (operation === 'manage') {
        await rpc('gt_manage_tournament',{p_nombre:fields.get('nombre'),p_slug:fields.get('slug'),p_modalidad:fields.get('modalidad'),p_fecha_limite:fields.get('fecha_limite')||null,p_abiertas:fields.get('abiertas')==='on',p_id:fields.get('torneo_id') ? Number(fields.get('torneo_id')) : null});
        location.assign(target(user.rol,fields.get('slug'))); return;
      }
      const params = {p_torneo: tournament.id};
      let saved = 'Cambios guardados.';
      if (operation === 'register') {
        await rpc('gt_register', {...params,p_nombre:fields.get('nombre'),p_curso:fields.get('curso')});
        form.reset(); saved = 'Tu equipo quedó inscrito correctamente.';
      } else if (operation === 'edit' || operation === 'delete') {
        await rpc('gt_edit', {...params,p_id:Number(form.dataset.id),p_delete:operation==='delete',p_nombre:fields.get('nombre'),p_curso:fields.get('curso')});
        saved = operation === 'delete' ? 'Inscripción eliminada.' : 'Inscripción actualizada.';
      } else if (operation === 'bracket') {
        await rpc('gt_bracket', {...params,p_equipos:fields.getAll('equipos').map(Number)});
        saved = 'Llaves guardadas. Ya puedes registrar los ganadores.';
      } else if (operation === 'winner') {
        await rpc('gt_winner', {...params,p_partido:Number(form.dataset.id),p_ganador:Number(fields.get('ganador'))});
        saved = 'Resultado guardado. Las siguientes rondas se actualizaron automáticamente.';
      } else if (operation === 'import') {
        const file = fields.get('archivo');
        if (!file || file.size > 131072) throw {code:'PT400',message:'Selecciona un archivo JSON de hasta 128 KB.'};
        let rows;
        try { rows = JSON.parse((await file.text()).replace(/^\uFEFF/, '')); }
        catch { throw {code:'PT400',message:'El archivo debe ser JSON válido.'}; }
        const count = await rpc('gt_import', {...params,p_rows:rows});
        saved = `Se importaron ${count} inscripciones. Los duplicados se omitieron.`;
      } else { throw new Error('Formulario no reconocido'); }
      // Confirmación del guardado antes de recargar: una falla de lectura no invita a duplicar el envío.
      toast(saved);
      try { await refresh(); }
      catch { toast('El cambio se guardó, pero no pudimos actualizar la vista. Recarga la página.', 'error'); }
    } catch (error) {
      if (form.id === 'loginForm') {
        const alert = document.createElement('div');
        alert.id = 'login-error'; alert.className = 'alert error'; alert.setAttribute('role','alert');
        alert.textContent = message(error); form.before(alert);
      } else toast(message(error), 'error');
    } finally { reset(form); }
  });

  const flash = sessionStorage.getItem('gt-flash');
  if (flash) { toast(flash, 'error'); sessionStorage.removeItem('gt-flash'); }
  try {
    const {data, error} = await client.auth.getUser();
    if (error && !['AuthSessionMissingError','AuthApiError'].includes(error.name)) throw error;
    if (!data.user) {
      if (expectedRole) { location.replace('index.html'); return; }
      status.hidden = true;
      return;
    }
    if (!expectedRole) {
      const state = await rpc('gt_state', {p_slug:null});
      location.replace(target(state.user.rol)); return;
    }
    await refresh();
  } catch (error) {
    status.textContent = message(error);
    const retry = document.createElement('button');
    retry.type = 'button'; retry.className = 'button secondary'; retry.textContent = 'Reintentar';
    retry.addEventListener('click', () => location.reload()); status.append(retry);
    if (!expectedRole) {
      // Permite entrar con otra cuenta si la sesión guardada carece de perfil.
      await client.auth.signOut({scope:'local'}).catch(() => {});
    }
  }
}
