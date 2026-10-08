'use strict';

// Contenido aportado por usuarios se representa con textContent, nunca innerHTML.
const menuToggle = document.querySelector('.menu-toggle');
const sidebar = document.querySelector('.sidebar');
const overlay = document.querySelector('.sidebar-overlay');
const sidebarClose = document.querySelector('.sidebar-close');
let previousFocus;

function setMenu(open) {
  if (!sidebar || !menuToggle) return;
  sidebar.classList.toggle('open', open);
  const mobile = !matchMedia('(min-width: 900px)').matches;
  sidebar.inert = mobile && !open;
  sidebar.setAttribute('aria-hidden', String(mobile && !open));
  menuToggle.setAttribute('aria-expanded', String(open));
  overlay.hidden = !open;
  document.body.style.overflow = open ? 'hidden' : '';
  if (open) {
    previousFocus = document.activeElement;
    sidebarClose.focus();
  } else if (previousFocus) previousFocus.focus();
}
menuToggle?.addEventListener('click', () => setMenu(!sidebar.classList.contains('open')));
sidebarClose?.addEventListener('click', () => setMenu(false));
overlay?.addEventListener('click', () => setMenu(false));
document.addEventListener('keydown', event => {
  if (!sidebar?.classList.contains('open')) return;
  if (event.key === 'Escape') setMenu(false);
  if (event.key === 'Tab') {
    const links = [...sidebar.querySelectorAll('a, button')].filter(el => el.getClientRects().length);
    const first = links[0], last = links[links.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});
matchMedia('(min-width: 900px)').addEventListener('change', event => {
  setMenu(false);
});
setMenu(false);

document.querySelector('.password-toggle')?.addEventListener('click', event => {
  const button = event.currentTarget;
  const field = document.getElementById('contrasena');
  const showing = field.type === 'password';
  field.type = showing ? 'text' : 'password';
  button.setAttribute('aria-pressed', String(showing));
  button.setAttribute('aria-label', showing ? 'Ocultar contraseña' : 'Mostrar contraseña');
});

document.addEventListener('click', event => event.target.closest('.toast-close')?.closest('.toast').remove());
document.addEventListener('click', event => {
  const button = event.target.closest('[data-edit]');
  if (!button) return;
  const form = document.getElementById(button.dataset.edit);
  form.hidden = !form.hidden;
  button.setAttribute('aria-expanded', String(!form.hidden));
  if (!form.hidden) form.querySelector('input:not([type=hidden])').focus();
});

const search = document.getElementById('tournament-search');
const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
search?.addEventListener('input', () => {
  const cards = [...document.querySelectorAll('[data-search]')];
  cards.forEach(card => { card.hidden = !normalize(card.dataset.search).includes(normalize(search.value.trim())); });
  document.querySelector('.empty-search').hidden = cards.some(card => !card.hidden);
});

const dialog = document.getElementById('confirm-dialog');
let pendingForm = null;
let pendingSubmitter = null;
dialog?.querySelector('[data-cancel]').addEventListener('click', () => dialog.close());
dialog?.addEventListener('close', () => { pendingForm = null; pendingSubmitter = null; });
dialog?.querySelector('[data-confirm]').addEventListener('click', () => {
  const form = pendingForm;
  const submitter = pendingSubmitter;
  dialog.close();
  if (form) {
    form.dataset.confirmed = 'true';
    form.requestSubmit(submitter || undefined);
  }
});

document.addEventListener('submit', event => {
    const form = event.target;
    if (event.defaultPrevented) return;
    if (form.classList.contains('loading')) { event.preventDefault(); return; }
    const teams = [...form.querySelectorAll('input[name=equipos]')];
    const size = Number(form.querySelector('[name=tamano]')?.value || 4);
    if (teams.length && teams.filter(input => input.checked).length !== size) {
      event.preventDefault();
      teams[0].setCustomValidity(`Selecciona exactamente ${size} participantes.`);
      teams[0].reportValidity();
      return;
    }
    if (form.dataset.confirm && form.dataset.confirmed !== 'true') {
      event.preventDefault();
      pendingForm = form;
      pendingSubmitter = event.submitter;
      document.getElementById('confirm-message').textContent = form.dataset.confirm;
      dialog.showModal();
      dialog.querySelector('[data-cancel]').focus();
      return;
    }
    form.classList.add('loading');
    form.setAttribute('aria-busy', 'true');
    // Se difiere el bloqueo para conservar los valores enviados del formulario.
    setTimeout(() => form.querySelectorAll('button[type=submit]').forEach(button => { button.disabled = true; }), 0);
 });
document.addEventListener('change', event => {
  if (event.target.matches('input[name=equipos], select[name=tamano]')) {
    const form = event.target.form;
    const boxes = [...form.querySelectorAll('input[name=equipos]')];
    boxes[0]?.setCustomValidity('');
    const selected = boxes.filter(input => input.checked).length;
    const size = Number(form.querySelector('[name=tamano]').value);
    form.querySelector('.selection-count').textContent = `${selected} de ${size} participantes seleccionados`;
  }
});
document.addEventListener('input', event => {
  if (event.target.id !== 'tournament-name') return;
  const slug = event.target.form.querySelector('[name=slug]');
  if (!slug.readOnly && !slug.dataset.edited) slug.value = normalize(event.target.value).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
});
document.addEventListener('input', event => {
  if (event.target.id === 'tournament-slug') event.target.dataset.edited = 'true';
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form.loading').forEach(form => {
    form.classList.remove('loading');
    form.removeAttribute('aria-busy');
    delete form.dataset.confirmed;
    form.querySelectorAll('button[type=submit]').forEach(button => { button.disabled = false; });
  });
});
