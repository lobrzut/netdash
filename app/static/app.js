const API = '';
let appVersion = null;
let buildDate = null;
let githubRepo = 'https://github.com/lobrzut/netdash';
let token = localStorage.getItem('netdash_token');
let services = [];
let apiKeys = [];
let notes = [];
let activeFilter = 'all';
let accessFilter = 'all';
let availabilityFilter = 'all';
let networkFilter = 'all';
let serviceSearch = '';
let appSettings = {};
let scanPollInterval = null;
let healthPollInterval = null;
let clockInterval = null;
let revealedKeys = new Set();
let currentPage = 'home';

const SERVICE_ICON_PRESETS = [
  'globe', 'lock', 'database', 'docker', 'chart', 'terminal', 'home', 'play', 'cloud', 'git',
  'shield', 'router', 'code', 'api', 'folder', 'mail', 'dns', 'ftp', 'monitor', 'queue',
  'search', 'storage', 'ai', 'dashboard', 'workflow', 'mqtt', 'nas', 'plug', 'download', 'tv',
  'film', 'photo', 'doc', 'wifi', 'ci', 'nginx', 'apache', 'python', 'windows', 'caddy', 'traefik',
];
const RECENT_ICONS_KEY = 'netdash_recent_icons';
const MAX_RECENT_ICONS = 8;
const SERVICE_ICON_GROUPS = [
  { id: 'all', labelKey: 'modal.edit.iconGroup.all' },
  { id: 'recent', labelKey: 'modal.edit.iconGroup.recent' },
  { id: 'media', labelKey: 'modal.edit.iconGroup.media', icons: ['play', 'tv', 'film', 'photo', 'download'] },
  {
    id: 'infra',
    labelKey: 'modal.edit.iconGroup.infra',
    icons: ['docker', 'database', 'storage', 'nas', 'cloud', 'router', 'dns', 'ftp', 'monitor', 'queue', 'wifi', 'plug', 'mqtt', 'home'],
  },
  { id: 'web', labelKey: 'modal.edit.iconGroup.web', icons: ['globe', 'nginx', 'apache', 'caddy', 'traefik', 'api', 'shield', 'lock', 'mail'] },
  {
    id: 'dev',
    labelKey: 'modal.edit.iconGroup.dev',
    icons: ['git', 'code', 'terminal', 'ci', 'python', 'windows', 'workflow', 'search', 'dashboard', 'ai', 'chart', 'folder', 'doc'],
  },
];
const iconPickerState = { edit: { group: 'all', query: '' }, add: { group: 'all', query: '' } };
const MAX_ICON_UPLOAD_BYTES = 2 * 1024 * 1024;
const ALLOWED_ICON_MIMES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml']);
const DEFAULT_SERVICE_CATEGORIES = [
  'Media', 'Monitoring', 'DevOps', 'Storage', 'Network', 'Home Automation', 'Urządzenie', 'Inne',
];

const $ = (sel) => document.querySelector(sel);

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

const TOAST_DURATION_MS = 3500;

function showToast(message, type = 'info') {
  if (!message) return;
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    container.setAttribute('aria-live', 'polite');
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'status');
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('toast-visible'));
  const dismiss = () => {
    toast.classList.remove('toast-visible');
    toast.classList.add('toast-out');
    setTimeout(() => toast.remove(), 280);
  };
  const timer = setTimeout(dismiss, TOAST_DURATION_MS);
  toast.addEventListener('click', () => {
    clearTimeout(timer);
    dismiss();
  });
}

const CATEGORY_ACCENTS = ['#22c55e', '#3b82f6', '#a855f7', '#f59e0b', '#ec4899', '#06b6d4', '#ef4444', '#84cc16'];

function categoryAccentColor(category) {
  const name = (category || 'Inne').trim();
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return CATEGORY_ACCENTS[Math.abs(hash) % CATEGORY_ACCENTS.length];
}
const $$ = (sel) => document.querySelectorAll(sel);

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (res.status === 401) {
    logout();
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    let detail = err.detail;
    if (Array.isArray(detail)) {
      detail = detail.map((d) => d.msg || d).join(', ');
    }
    throw new Error(translateApiDetail(detail) || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function showView(id) {
  $$('.view').forEach((v) => v.classList.add('hidden'));
  $(`#${id}`).classList.remove('hidden');
}

function logout() {
  token = null;
  localStorage.removeItem('netdash_token');
  showView('login-view');
  if (scanPollInterval) clearInterval(scanPollInterval);
  if (healthPollInterval) clearInterval(healthPollInterval);
}

function showLoginError(message) {
  const errEl = $('#login-error');
  errEl.textContent = message;
  errEl.classList.remove('hidden');
}

function showDashboardError(message) {
  const el = $('#dashboard-error');
  if (!el) return;
  if (!message) {
    el.classList.add('hidden');
    el.textContent = '';
    return;
  }
  el.textContent = message;
  el.classList.remove('hidden');
}

function handleDashboardLoadError(err) {
  if (err?.message === 'Unauthorized') return;
  token = null;
  localStorage.removeItem('netdash_token');
  showView('login-view');
  showLoginError(t('error.dashboardLoad', {
    detail: err?.message || t('error.unknown'),
    host: location.hostname,
  }));
}

function formatVersion(version) {
  if (!version) return '—';
  return version.startsWith('v') ? version : `v${version}`;
}

function applyVersionDisplay() {
  const ver = formatVersion(appVersion);
  ['#app-version', '#login-version', '#settings-app-version'].forEach((sel) => {
    const el = $(sel);
    if (el) {
      el.textContent = ver;
      if (sel === '#settings-app-version') el.title = ver;
    }
  });
  const buildEl = $('#settings-build-date');
  const buildChip = $('#settings-build-chip');
  if (buildEl) buildEl.textContent = buildDate || '—';
  if (buildChip) buildChip.hidden = !buildDate;
  const githubEl = $('#settings-github-link');
  if (githubEl && githubRepo) githubEl.href = githubRepo;
}

function authorInitials(name) {
  const clean = String(name || 'lobrzut').replace(/^@/, '').trim();
  if (!clean) return 'ND';
  const parts = clean.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return clean.slice(0, 2).toUpperCase();
}

function renderAboutPanel() {
  const prose = $('#about-prose-text');
  if (prose) prose.textContent = ($('#settings-about-project')?.value || appSettings.about_project || '').trim();

  const wrap = $('#about-prose-wrap');
  if (wrap && prose) {
    wrap.classList.remove('about-prose-wrap--clamped');
    if (prose.textContent.length > 420) wrap.classList.add('about-prose-wrap--clamped');
  }

  const name = ($('#settings-author-name')?.value || appSettings.author_name || 'lobrzut').trim();
  const url = ($('#settings-author-url')?.value || appSettings.author_url || githubRepo || 'https://github.com/lobrzut').trim();
  const handle = name.startsWith('@') ? name : `@${name}`;
  const link = $('#about-author-link');
  if (link) {
    link.textContent = handle;
    link.href = url || 'https://github.com/lobrzut';
  }
  const avatar = $('#about-author-avatar');
  if (avatar) avatar.textContent = authorInitials(name);
}

function updateFooterNetwork(netLabel) {
  const footer = $('#network-badge-footer');
  if (!footer) return;
  if (netLabel) footer.dataset.net = netLabel;
  const net = footer.dataset.net || '—';
  const footerExtra = appSettings.footer_text ? ` · ${appSettings.footer_text}` : '';
  footer.textContent = net + footerExtra;
}

async function checkServerHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data.ok) throw new Error(t('error.serverHealth'));
    appVersion = data.version || null;
    buildDate = data.build_date || null;
    if (data.github) githubRepo = data.github;
    applyVersionDisplay();
    $('#login-error').classList.add('hidden');
    return data;
  } catch (err) {
    showLoginError(t('error.noConnection', { host: location.hostname, detail: err.message }));
    return null;
  }
}

async function login(username, password) {
  const data = await api('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  token = data.access_token;
  localStorage.setItem('netdash_token', token);
  showView('dashboard-view');
  await loadDashboard();
}

async function setLanguage(lang) {
  await loadLanguage(lang);
  applyI18n();
  $('#settings-language').value = lang;
  renderAccessFilters();
  renderAvailabilityFilters();
  if (currentPage === 'home') renderPinnedServices();
  else renderServices();
  renderKeys();
  renderNotes();
}

function gridDensityClass() {
  const density = appSettings.services_columns || 'normal';
  if (density === 'compact') return 'services-grid--compact';
  if (density === 'comfortable') return 'services-grid--comfortable';
  return '';
}

function sanitizeCustomCss(css) {
  if (!css) return '';
  let cleaned = css.replace(/<\s*script[^>]*>[\s\S]*?<\s*\/\s*script\s*>/gi, '');
  cleaned = cleaned.replace(/@import\s+[^;]+;?/gi, '');
  cleaned = cleaned.replace(/javascript\s*:/gi, '');
  cleaned = cleaned.replace(/expression\s*\(/gi, '');
  return cleaned.trim();
}

function applyCustomCss(css) {
  let el = $('#custom-css-inject');
  if (!el) {
    el = document.createElement('style');
    el.id = 'custom-css-inject';
    document.head.appendChild(el);
  }
  el.textContent = sanitizeCustomCss(css);
}

function applyFavicon(url) {
  const href = (url || '').trim() || '/static/favicon.svg';
  let link = document.querySelector('link[rel="icon"]');
  if (!link) {
    link = document.createElement('link');
    link.rel = 'icon';
    document.head.appendChild(link);
  }
  link.href = href;
}

function applyCustomLogo() {
  const url = appSettings.use_custom_logo && appSettings.custom_logo_url
    ? appSettings.custom_logo_url
    : null;
  document.querySelectorAll('.logo-icon, .logo-small').forEach((box) => {
    let custom = box.querySelector('img.custom-logo');
    const brand = box.querySelector('img.brand-logo');
    if (url) {
      if (!custom) {
        custom = document.createElement('img');
        custom.className = 'custom-logo';
        custom.alt = '';
        custom.decoding = 'async';
        box.appendChild(custom);
      }
      custom.src = url;
      custom.classList.remove('hidden');
      brand?.classList.add('hidden');
    } else {
      custom?.classList.add('hidden');
      brand?.classList.remove('hidden');
    }
  });
}

function isPinnedClassicLayout(layout) {
  return layout === 'classic' || layout === 'classic-sm';
}

function dashboardLayout() {
  const layout = appSettings.pinned_card_size || 'medium';
  if (layout === 'large') return 'classic';
  if (layout === 'normal') return 'medium';
  if (['classic', 'classic-sm', 'medium', 'compact'].includes(layout)) return layout;
  return 'medium';
}

function applyDashboardLayout() {
  document.body.setAttribute('data-dashboard-layout', dashboardLayout());
}

function applyLayout() {
  applyDashboardLayout();
  $('#widget-clock')?.classList.toggle('hidden', appSettings.show_clock === false);
  $('#widget-vault')?.classList.toggle('hidden', appSettings.show_vault === false);
  $('#widget-notes')?.classList.toggle('hidden', appSettings.show_notes === false);
  const showStats = appSettings.show_stats !== false && currentPage === 'services';
  $('#stats')?.classList.toggle('hidden', !showStats);
  $('#category-filters')?.classList.toggle('hidden', appSettings.show_category_filters === false);
  const onServices = currentPage === 'services';
  const servicesSlot = document.querySelector('.header-actions-services');
  if (servicesSlot) {
    servicesSlot.setAttribute('aria-hidden', onServices ? 'false' : 'true');
  }
  document.querySelectorAll('.header-services-only').forEach((el) => {
    el.tabIndex = onServices ? 0 : -1;
  });
  updateFooterNetwork();
}

function navigateTo(page) {
  if (page !== 'home' && page !== 'services') return;
  currentPage = page;
  localStorage.setItem('netdash_page', page);
  $('#dashboard-view')?.setAttribute('data-page', page);
  $('#page-home')?.classList.toggle('hidden', page !== 'home');
  $('#page-services')?.classList.toggle('hidden', page !== 'services');
  document.querySelectorAll('.nav-segment-btn').forEach((btn) => {
    const active = btn.dataset.page === page;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  applyLayout();
  window.scrollTo(0, 0);
  if (page === 'home') renderPinnedServices();
  else renderServices();
}

function setAccentColor(hex) {
  document.documentElement.style.setProperty('--accent', hex);
  document.documentElement.style.setProperty('--accent-bright', hex);
  document.documentElement.style.setProperty('--accent-soft', `${hex}1f`);
  document.documentElement.style.setProperty('--accent-glow', `${hex}4d`);
  document.documentElement.style.setProperty('--highlight', hex);
}

const VALID_THEMES = ['midnight', 'ocean', 'ember', 'nord', 'light', 'homer'];
const DEFAULT_THEME = 'midnight';

function normalizeTheme(theme) {
  return VALID_THEMES.includes(theme) ? theme : DEFAULT_THEME;
}

function applyDataTheme(theme) {
  const t = normalizeTheme(theme);
  document.documentElement.setAttribute('data-theme', t);
  try {
    localStorage.setItem('netdash_theme', t);
  } catch {
    /* ignore storage errors */
  }
}

function getSelectedTheme() {
  const active = $('#settings-theme-picker .theme-card.active');
  return normalizeTheme(active?.dataset.theme || appSettings.theme || DEFAULT_THEME);
}

function updateThemePickerSelection(theme) {
  const t = normalizeTheme(theme);
  $$('#settings-theme-picker .theme-card').forEach((btn) => {
    const active = btn.dataset.theme === t;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
}

function updateAccentHex() {
  const hex = $('#settings-accent')?.value || '#22c55e';
  const el = $('#settings-accent-hex');
  if (el) el.textContent = hex;
}

function applyTheme() {
  applyDataTheme(appSettings.theme || DEFAULT_THEME);
  const hex = appSettings.accent_color || '#22c55e';
  setAccentColor(hex);
  document.title = `${appSettings.title || 'NetDash'} — ${t('app.titleSuffix')}`;
  $('#app-title').textContent = appSettings.title || 'NetDash';
  $('#login-title').textContent = appSettings.title || 'NetDash';
  $('#app-subtitle').textContent = appSettings.subtitle || t('app.tagline');
  $('#login-subtitle').textContent = appSettings.subtitle || t('app.tagline');
  applyCustomCss(appSettings.custom_css || '');
  applyFavicon(appSettings.favicon_url);
  applyCustomLogo();
  applyLayout();
}

const DEFAULT_SETTINGS = {
  title: 'NetDash',
  subtitle: '',
  language: 'pl',
  theme: 'midnight',
  accent_color: '#22c55e',
  show_vault: true,
  show_notes: true,
  show_clock: true,
  show_stats: true,
  show_category_filters: true,
  show_service_urls: true,
  show_ports: true,
  services_grouped: true,
  services_columns: 'normal',
  default_access_filter: 'all',
  card_style: 'detailed',
  pinned_card_size: 'medium',
  show_about: false,
  full_scan_default: false,
  host_scan_ports: '22,445,3389,5900',
  host_only_entries: true,
};

async function fetchSettings() {
  try {
    return await api('/api/settings');
  } catch {
    return { ...DEFAULT_SETTINGS, ...(appSettings || {}) };
  }
}

function updateDockerScanWarning(netRes, settings) {
  const el = $('#docker-scan-warning');
  if (!el) return;
  const show = netRes?.docker_bridge
    && !netRes?.scan_cidr_configured
    && !settings?.scan_cidr_default;
  if (!show) {
    el.classList.add('hidden');
    el.textContent = '';
    return;
  }
  el.textContent = t('settings.dockerScanWarning', {
    ip: netRes.local_ip,
    network: netRes.local_network,
  });
  el.classList.remove('hidden');
}

function normalizeService(s) {
  return {
    ...s,
    has_login: !!s.has_login,
    wol_enabled: !!s.wol_enabled,
    pinned: !!s.pinned,
    customized: !!s.customized,
  };
}

function isServiceOnline(s) {
  return s.is_online === true || s.is_online === null;
}

async function loadServices() {
  const fresh = await api('/api/services');
  services = fresh.map(normalizeService);
  refreshServiceViews();
}

function refreshServiceViews() {
  updateStats();
  renderPinnedServices();
  if (currentPage === 'services') renderServices();
}

async function loadDashboard() {
  showDashboardError('');
  const [svcRes, netRes, keysRes, notesRes, settings] = await Promise.all([
    api('/api/services').catch((e) => ({ error: e })),
    api('/api/network').catch((e) => ({ error: e })),
    api('/api/keys').catch((e) => ({ error: e })),
    api('/api/notes').catch((e) => ({ error: e })),
    fetchSettings(),
  ]);

  const errors = [];
  if (svcRes?.error) errors.push(`${t('error.api.services')}: ${svcRes.error.message}`);
  if (netRes?.error) errors.push(`${t('error.api.network')}: ${netRes.error.message}`);
  if (keysRes?.error) errors.push(`${t('error.api.keys')}: ${keysRes.error.message}`);
  if (notesRes?.error) errors.push(`${t('error.api.notes')}: ${notesRes.error.message}`);
  if (errors.length === 4) throw new Error(errors.join('; '));

  services = (svcRes?.error ? [] : svcRes).map(normalizeService);
  apiKeys = keysRes?.error ? [] : keysRes;
  notes = notesRes?.error ? [] : notesRes;
  appSettings = settings;
  applyDefaultAccessFilter(settings.default_access_filter);
  await setLanguage(settings.language || 'pl');
  applyTheme();

  if (netRes?.error) {
    showDashboardError(t('error.partialApi', { errors: errors.join('; ') }));
  } else {
    window.__netdashNetwork = netRes;
    const netLabel = `${netRes.local_ip} · ${netRes.local_network}`;
    updateFooterNetwork(netLabel);
    $('#clock-network').textContent = netLabel;
    $('#local-network-hint').textContent = t('hint.localNetwork', { network: netRes.local_network });
    $('#cidr-input').placeholder = netRes.local_network;
    updateDockerScanWarning(netRes, settings);
  }

  $('#full-scan').checked = !!settings.full_scan_default;
  if (settings.scan_cidr_default) $('#cidr-input').placeholder = settings.scan_cidr_default;
  updateStats();
  navigateTo(localStorage.getItem('netdash_page') || 'home');
  startClock();
  startHealthPolling();
}

let serviceRefreshInterval = null;

function startHealthPolling() {
  if (healthPollInterval) clearInterval(healthPollInterval);
  if (serviceRefreshInterval) clearInterval(serviceRefreshInterval);
  if (appSettings.health_check_enabled === false) return;
  const intervalSec = Math.max(15, Math.min(900, appSettings.health_check_interval || 60));
  const interval = intervalSec * 1000;
  const refreshMs = Math.max(30000, Math.floor(interval / 2));
  serviceRefreshInterval = setInterval(() => {
    loadServices().catch(() => {});
  }, refreshMs);
  healthPollInterval = setInterval(async () => {
    try {
      await api('/api/services/health-check', { method: 'POST' });
      await loadServices();
    } catch {
      /* ignore background refresh errors */
    }
  }, interval);
}

function updateStats() {
  $('#stat-total').textContent = services.length;
  $('#stat-online').textContent = services.filter(serviceIsOnlineHealthy).length;
  $('#stat-login').textContent = services.filter((s) => s.has_login === true).length;
  $('#stat-keys').textContent = apiKeys.length;
  $('#stat-notes').textContent = notes.length;
}

function startClock() {
  if (clockInterval) clearInterval(clockInterval);
  const tick = () => {
    const now = new Date();
    const locale = DATE_LOCALES[currentLang] || 'en-GB';
    $('#clock-time').textContent = now.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    $('#clock-date').textContent = now.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  };
  tick();
  clockInterval = setInterval(tick, 1000);
}

function simpleMarkdown(text) {
  if (!text) return '';
  let html = esc(text);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/^- (.+)$/gm, '• $1');
  return html;
}

const DATE_LOCALES = { pl: 'pl-PL', en: 'en-GB', de: 'de-DE', uk: 'uk-UA' };

function parseISODate(iso) {
  if (!iso) return null;
  const raw = String(iso).trim();
  if (!raw) return null;
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T');
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return null;
  const y = d.getFullYear();
  if (y < 1970 || y > 2100) return null;
  return d;
}

function formatDate(iso) {
  const d = parseISODate(iso);
  if (!d) return '—';
  const locale = DATE_LOCALES[appSettings.language] || DATE_LOCALES.pl;
  return d.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' });
}

function noteSortKey(n) {
  const d = parseISODate(n.updated_at) || parseISODate(n.created_at);
  return d ? d.getTime() : 0;
}

function notePreviewText(n) {
  const raw = (n.content || '').trim();
  if (!raw) return '';
  return raw.replace(/\s+/g, ' ');
}

function isWolDevice(s) {
  return !!s.wol_enabled && !!s.mac_address;
}

function renderNoteCard(n) {
  const title = (n.title || '').trim() || t('notes.untitled');
  const preview = notePreviewText(n);
  const previewHtml = preview
    ? `<div class="note-tile-preview">${esc(preview)}</div>`
    : `<div class="note-tile-preview note-tile-preview--empty">—</div>`;
  return `
    <div class="note-tile note-${n.color} ${n.pinned ? 'pinned' : ''}" data-id="${n.id}" role="button" tabindex="0" title="${esc(title)}">
      ${n.pinned ? `<span class="note-tile-pin" title="${t('notes.pinned')}" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor" width="10" height="10"><path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z"/></svg></span>` : ''}
      <div class="note-tile-title">${esc(title)}</div>
      ${previewHtml}
    </div>`;
}

function renderKeys() {
  const query = ($('#keys-search').value || '').toLowerCase();
  const filtered = apiKeys.filter((k) => {
    const hay = `${k.name} ${k.service} ${k.username || ''} ${k.notes || ''}`.toLowerCase();
    return hay.includes(query);
  });

  const list = $('#keys-list');
  if (filtered.length === 0) {
    list.innerHTML = `<div class="widget-empty">${t('widget.empty.keys')}</div>`;
    return;
  }

  list.innerHTML = filtered.map((k) => {
    const revealed = revealedKeys.has(k.id);
    const secretDisplay = revealed ? esc(k._revealed || '...') : esc(k.secret_masked);
    return `
    <div class="key-item ${k.pinned ? 'pinned' : ''}" data-id="${k.id}">
      <div class="key-info">
        <div class="key-name">${k.pinned ? '📌 ' : ''}${esc(k.name)}</div>
        <div class="key-meta">${esc(k.service)}${k.username ? ` · ${esc(k.username)}` : ''}</div>
        <div class="key-secret" data-secret>${secretDisplay}</div>
        ${k.notes ? `<div class="key-meta">${esc(k.notes)}</div>` : ''}
      </div>
      <div class="key-actions">
        <button class="btn-icon btn-icon-sm key-copy" title="${t('action.copy')}" data-id="${k.id}">⎘</button>
        <button class="btn-icon btn-icon-sm key-reveal" title="${revealed ? t('action.hide') : t('action.show')}" data-id="${k.id}">${revealed ? '◉' : '◎'}</button>
        <button class="btn-icon btn-icon-sm key-edit" title="${t('action.edit')}" data-id="${k.id}">✎</button>
        <button class="btn-icon btn-icon-sm key-delete" title="${t('modal.delete')}" data-id="${k.id}">×</button>
      </div>
    </div>`;
  }).join('');

  list.querySelectorAll('.key-copy').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const data = await api(`/api/keys/${btn.dataset.id}/reveal`);
      await navigator.clipboard.writeText(data.secret);
      btn.textContent = '✓';
      setTimeout(() => { btn.textContent = '⎘'; }, 1500);
    });
  });

  list.querySelectorAll('.key-reveal').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = Number(btn.dataset.id);
      if (revealedKeys.has(id)) {
        revealedKeys.delete(id);
        renderKeys();
        return;
      }
      const data = await api(`/api/keys/${id}/reveal`);
      const key = apiKeys.find((k) => k.id === id);
      if (key) key._revealed = data.secret;
      revealedKeys.add(id);
      renderKeys();
    });
  });

  list.querySelectorAll('.key-edit').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openKeyModal(Number(btn.dataset.id));
    });
  });

  list.querySelectorAll('.key-delete').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm(t('confirm.delete.key'))) return;
      await api(`/api/keys/${btn.dataset.id}`, { method: 'DELETE' });
      revealedKeys.delete(Number(btn.dataset.id));
      await loadDashboard();
    });
  });
}

function renderNotes() {
  const query = ($('#notes-search').value || '').toLowerCase().trim();
  const filtered = notes.filter((n) => {
    const hay = `${n.title} ${n.content}`.toLowerCase();
    return hay.includes(query);
  });

  const countEl = $('#notes-count');
  if (countEl) {
    countEl.textContent = query && filtered.length !== notes.length
      ? `${filtered.length}/${notes.length}`
      : String(notes.length);
    countEl.classList.toggle('hidden', notes.length === 0);
  }

  const list = $('#notes-list');
  if (notes.length === 0) {
    list.innerHTML = `<div class="widget-empty notes-empty">${t('widget.empty.notes')}</div>`;
    return;
  }
  if (filtered.length === 0) {
    list.innerHTML = `<div class="widget-empty notes-empty">${t('widget.empty.notesSearch')}</div>`;
    return;
  }

  const pinned = filtered.filter((n) => n.pinned).sort((a, b) => noteSortKey(b) - noteSortKey(a));
  const unpinned = filtered.filter((n) => !n.pinned).sort((a, b) => noteSortKey(b) - noteSortKey(a));

  let html = '';
  if (pinned.length > 0) {
    html += `
      <section class="notes-group">
        <h3 class="notes-group-label">${t('notes.group.pinned')}<span class="notes-group-count">${pinned.length}</span></h3>
        <div class="notes-tiles-grid">${pinned.map(renderNoteCard).join('')}</div>
      </section>`;
  }
  if (unpinned.length > 0) {
    html += `
      <section class="notes-group">
        ${pinned.length > 0 ? `<h3 class="notes-group-label">${t('notes.group.other')}<span class="notes-group-count">${unpinned.length}</span></h3>` : ''}
        <div class="notes-tiles-grid">${unpinned.map(renderNoteCard).join('')}</div>
      </section>`;
  }

  list.innerHTML = html;

  list.querySelectorAll('.note-tile').forEach((tile) => {
    const open = () => openNoteModal(Number(tile.dataset.id));
    tile.addEventListener('click', open);
    tile.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        open();
      }
    });
  });
}

function openKeyModal(editId = null) {
  $('#key-edit-id').value = editId || '';
  $('#key-modal-title').textContent = editId ? t('modal.edit.key') : t('modal.add.key');
  $('#key-secret-hint').classList.toggle('hidden', !editId);

  if (editId) {
    const key = apiKeys.find((k) => k.id === editId);
    if (!key) return;
    $('#key-name').value = key.name;
    $('#key-service').value = key.service;
    $('#key-secret').value = '';
    $('#key-username').value = key.username || '';
    $('#key-url').value = key.url || '';
    $('#key-notes').value = key.notes || '';
    $('#key-pinned').checked = key.pinned;
  } else {
    $('#key-name').value = '';
    $('#key-service').value = '';
    $('#key-secret').value = '';
    $('#key-username').value = '';
    $('#key-url').value = '';
    $('#key-notes').value = '';
    $('#key-pinned').checked = false;
    $('#key-secret-hint').classList.add('hidden');
  }
  openModal('key-modal');
}

function openNoteModal(editId = null) {
  $('#note-edit-id').value = editId || '';
  $('#note-modal-title').textContent = editId ? t('modal.edit.note') : t('modal.add.note');
  $('#note-delete').classList.toggle('hidden', !editId);

  if (editId) {
    const note = notes.find((n) => n.id === editId);
    if (!note) return;
    $('#note-title').value = note.title;
    $('#note-content').value = note.content;
    $('#note-color').value = note.color;
    $('#note-pinned').checked = note.pinned;
  } else {
    $('#note-title').value = '';
    $('#note-content').value = '';
    $('#note-color').value = 'green';
    $('#note-pinned').checked = false;
  }
  openModal('note-modal');
}

async function saveKey() {
  const editId = $('#key-edit-id').value;
  const payload = {
    name: $('#key-name').value.trim(),
    service: $('#key-service').value.trim() || t('modal.key.other'),
    username: $('#key-username').value.trim() || null,
    url: $('#key-url').value.trim() || null,
    notes: $('#key-notes').value.trim() || null,
    pinned: $('#key-pinned').checked,
  };
  const secret = $('#key-secret').value;
  if (!payload.name) return showToast(t('alert.keyName'));
  if (!editId && !secret) return showToast(t('alert.keySecret'));

  if (editId) {
    if (secret) payload.secret = secret;
    await api(`/api/keys/${editId}`, { method: 'PATCH', body: JSON.stringify(payload) });
  } else {
    payload.secret = secret;
    await api('/api/keys', { method: 'POST', body: JSON.stringify(payload) });
  }
  closeModal('key-modal');
  await loadDashboard();
}

async function saveNote() {
  const editId = $('#note-edit-id').value;
  const payload = {
    title: $('#note-title').value.trim(),
    content: $('#note-content').value,
    color: $('#note-color').value,
    pinned: $('#note-pinned').checked,
  };
  if (!payload.title) return showToast(t('alert.noteTitle'));

  if (editId) {
    await api(`/api/notes/${editId}`, { method: 'PATCH', body: JSON.stringify(payload) });
  } else {
    await api('/api/notes', { method: 'POST', body: JSON.stringify(payload) });
  }
  closeModal('note-modal');
  await loadDashboard();
}

function syncServiceSearchFromDom() {
  const input = $('#services-search');
  if (input) serviceSearch = input.value;
}

function applyDefaultAccessFilter(value) {
  const v = value || 'all';
  if (v === 'offline') {
    accessFilter = 'all';
    availabilityFilter = 'offline';
    return;
  }
  accessFilter = v;
}

function filterByAccess(list, access = accessFilter) {
  if (access === 'login') return list.filter((s) => s.has_login);
  if (access === 'public') return list.filter((s) => !s.has_login);
  if (access === 'wol') return list.filter(isWolDevice);
  if (access === 'pinned') return list.filter((s) => s.pinned);
  return list;
}

function serviceAvailabilityBucket(s) {
  const state = serviceHealthState(s);
  if (state === 'offline' || state === 'error') return 'offline';
  if (state === 'online') return 'online';
  return 'unknown';
}

function filterByAvailability(list, availability = availabilityFilter) {
  if (availability === 'all') return list;
  return list.filter((s) => serviceAvailabilityBucket(s) === availability);
}

function filterByNetwork(list, network = networkFilter) {
  if (network === 'all') return list;
  return list.filter((s) => hostToSubnet(s.host) === network);
}

function filterByCategory(list, category = activeFilter) {
  if (category === 'all' || appSettings.show_category_filters === false) return list;
  return list.filter((s) => s.category === category);
}

function filterBySearch(list, q = serviceSearch) {
  const trimmed = (q || '').trim();
  if (!trimmed) return list;
  return list.filter((s) => serviceMatchesSearch(s, trimmed));
}

function applyServiceFilters(list, opts = {}) {
  const {
    access = accessFilter,
    availability = availabilityFilter,
    network = networkFilter,
    category = activeFilter,
    search = serviceSearch,
  } = opts;
  return filterByCategory(
    filterByNetwork(
      filterByAvailability(filterByAccess(filterBySearch(list, search), access), availability),
      network,
    ),
    category,
  );
}

function normalizeFilterState() {
  syncServiceSearchFromDom();
  const searchBase = filterBySearch(services);

  if (networkFilter !== 'all') {
    const inSubnet = filterByAccess(searchBase).filter(
      (s) => hostToSubnet(s.host) === networkFilter,
    );
    if (inSubnet.length === 0) networkFilter = 'all';
  }

  if (activeFilter !== 'all' && appSettings.show_category_filters !== false) {
    const categoryBase = filterByNetwork(filterByAccess(searchBase), networkFilter);
    if (!categoryBase.some((s) => s.category === activeFilter)) {
      activeFilter = 'all';
    }
  }

  if (accessFilter === 'pinned') {
    const accessBase = filterByCategory(
      filterByAvailability(filterByNetwork(filterBySearch(services), networkFilter), availabilityFilter),
      activeFilter,
    );
    if (!accessBase.some((s) => s.pinned)) accessFilter = 'all';
  }

  if (availabilityFilter !== 'all') {
    const availabilityBase = filterByCategory(
      filterByNetwork(filterByAccess(filterBySearch(services)), networkFilter),
      activeFilter,
    );
    if (!availabilityBase.some((s) => serviceAvailabilityBucket(s) === availabilityFilter)) {
      availabilityFilter = 'all';
    }
  }
}

function applyAccessFilter(list) {
  return filterByAccess(list);
}

function hostToSubnet(host) {
  if (!host) return null;
  const parts = host.split('.');
  if (parts.length !== 4) return null;
  const nums = parts.map((p) => parseInt(p, 10));
  if (nums.some((n) => Number.isNaN(n) || n < 0 || n > 255)) return null;
  return `${parts[0]}.${parts[1]}.${parts[2]}.0/24`;
}

function cidrToSubnet24(cidr) {
  if (!cidr) return null;
  const first = cidr.split(/[\s,;]+/).find(Boolean);
  return first ? hostToSubnet(first.split('/')[0]) : null;
}

function parseScanCidrs(cidrText) {
  if (!cidrText) return [];
  const subnets = new Set();
  cidrText.split(/[\s,;]+/).filter(Boolean).forEach((part) => {
    const subnet = cidrToSubnet24(part);
    if (subnet) subnets.add(subnet);
  });
  return [...subnets];
}

function getLocalNetworkSubnet() {
  return cidrToSubnet24(window.__netdashNetwork?.local_network);
}

function collectNetworkSubnets(serviceList) {
  const counts = {};
  serviceList.forEach((s) => {
    const subnet = hostToSubnet(s.host);
    if (subnet) counts[subnet] = (counts[subnet] || 0) + 1;
  });
  const localSubnet = getLocalNetworkSubnet();
  if (localSubnet && !(localSubnet in counts)) counts[localSubnet] = 0;
  const scanSubnets = parseScanCidrs(appSettings.scan_cidr_default);
  scanSubnets.forEach((subnet) => {
    if (!(subnet in counts)) counts[subnet] = 0;
  });
  return counts;
}

function applyNetworkFilter(list) {
  return filterByNetwork(list);
}

function serviceSearchHaystack(s) {
  const url = (s.url || '').toLowerCase();
  const host = (s.host || '').toLowerCase();
  const name = (s.name || '').toLowerCase();
  const cat = (s.category || '').toLowerCase();
  const desc = (s.description || '').toLowerCase();
  const proto = (s.protocol || '').toLowerCase();
  const port = String(s.port || '');
  const urlHost = url.replace(/^https?:\/\//, '').split('/')[0];
  return `${name} ${url} ${host} ${cat} ${desc} ${proto} ${urlHost} :${port}`;
}

function normalizeServiceSearchTerms(q) {
  const raw = q.trim().toLowerCase();
  if (!raw) return [];
  const terms = new Set([raw]);
  const noProto = raw.replace(/^https?:\/\//, '').replace(/\/+$/, '');
  if (noProto) terms.add(noProto);
  const hostPort = noProto.split('/')[0];
  if (hostPort) terms.add(hostPort);
  const hostOnly = hostPort.replace(/:\d+$/, '');
  if (hostOnly && hostOnly !== hostPort) terms.add(hostOnly);
  const ipMatch = hostPort.match(/\d{1,3}(?:\.\d{1,3}){3}/);
  if (ipMatch) terms.add(ipMatch[0]);
  const portMatch = raw.match(/:(\d+)/) || hostPort.match(/:(\d+)/);
  if (portMatch) terms.add(`:${portMatch[1]}`);
  return [...terms].filter(Boolean);
}

function serviceMatchesSearch(s, q) {
  const terms = normalizeServiceSearchTerms(q);
  if (!terms.length) return true;
  const hay = serviceSearchHaystack(s);
  return terms.some((term) => hay.includes(term));
}

function applyServiceSearch(list) {
  return filterBySearch(list);
}

function applyCategoryFilter(list) {
  return filterByCategory(list);
}

function countHiddenByFilters(searchMatches) {
  return searchMatches.length - applyServiceFilters(searchMatches).length;
}

function renderSearchFilterHint(hiddenCount) {
  let el = $('#services-search-hint');
  if (!hiddenCount) {
    if (el) el.classList.add('hidden');
    return;
  }
  if (!el) {
    el = document.createElement('p');
    el.id = 'services-search-hint';
    el.className = 'services-search-hint';
    $('#services-container').parentNode.insertBefore(el, $('#services-container'));
  }
  el.textContent = t('empty.services.searchHidden', { count: hiddenCount });
  el.classList.remove('hidden');
}

function updateServicesEmptyState(hiddenByFilter = 0) {
  const empty = $('#empty-state');
  const title = $('#empty-title');
  const hint = $('#empty-hint');
  const icon = empty?.querySelector('.empty-icon');
  const clearBtn = $('#empty-clear-search');
  const q = serviceSearch.trim();

  empty.classList.remove('hidden');

  if (services.length === 0) {
    icon?.classList.remove('empty-icon--search');
    title.textContent = t('empty.services');
    hint.textContent = t('empty.services.hint');
    hint.classList.remove('hidden');
    clearBtn?.classList.add('hidden');
    return;
  }

  if (q) {
    icon?.classList.add('empty-icon--search');
    title.innerHTML = t('empty.services.searchTitle');
    hint.innerHTML = t('empty.services.searchHint', { query: `<strong>${esc(q)}</strong>` });
    hint.classList.remove('hidden');
    if (hiddenByFilter > 0) {
      hint.innerHTML += `<br><span class="empty-filter-note">${esc(t('empty.services.searchHidden', { count: hiddenByFilter }))}</span>`;
    }
    clearBtn?.classList.remove('hidden');
    return;
  }

  icon?.classList.remove('empty-icon--search');
  clearBtn?.classList.add('hidden');
  title.textContent = t('empty.services.filter');
  if (accessFilter === 'wol') {
    const missingMac = services.filter((s) => !s.mac_address).length;
    hint.textContent = missingMac > 0
      ? t('empty.filter.wolMissingMac', { count: missingMac })
      : t('empty.filter.wol');
    hint.classList.remove('hidden');
  } else if (availabilityFilter === 'offline') {
    hint.textContent = t('empty.filter.offline');
    hint.classList.remove('hidden');
  } else if (availabilityFilter === 'online') {
    hint.textContent = t('empty.filter.online');
    hint.classList.remove('hidden');
  } else if (accessFilter === 'pinned') {
    hint.textContent = t('empty.filter.pinned');
    hint.classList.remove('hidden');
  } else {
    hint.classList.add('hidden');
  }
}

function renderAccessFilters() {
  const allCount = applyServiceFilters(services, { access: 'all' }).length;
  const loginCount = applyServiceFilters(services, { access: 'login' }).length;
  const publicCount = applyServiceFilters(services, { access: 'public' }).length;
  const wolCount = applyServiceFilters(services, { access: 'wol' }).length;
  const pinnedCount = applyServiceFilters(services, { access: 'pinned' }).length;
  const accessAllActive = accessFilter === 'all' && availabilityFilter === 'all';
  const accessAllSuppressed = accessFilter === 'all' && availabilityFilter !== 'all';
  const container = $('#access-filters');
  container.innerHTML = [
    `<button type="button" class="filter-chip ${accessAllActive ? 'active' : ''} ${accessAllSuppressed ? 'filter-suppressed' : ''}" data-access="all" title="${accessAllSuppressed ? t('filter.allSuppressedHint') : ''}"><span class="chip-label">${t('filter.all')}</span><span class="count">${allCount}</span></button>`,
    `<button type="button" class="filter-chip filter-login ${accessFilter === 'login' ? 'active' : ''}" data-access="login"><span class="chip-label"><span class="chip-icon" aria-hidden="true">🔐</span>${t('filter.login')}</span><span class="count">${loginCount}</span></button>`,
    `<button type="button" class="filter-chip filter-public ${accessFilter === 'public' ? 'active' : ''}" data-access="public"><span class="chip-label"><span class="chip-icon" aria-hidden="true">🌐</span>${t('filter.public')}</span><span class="count">${publicCount}</span></button>`,
    `<button type="button" class="filter-chip filter-wol ${accessFilter === 'wol' ? 'active' : ''}" data-access="wol"><span class="chip-label"><span class="chip-icon" aria-hidden="true">⚡</span>${t('filter.wol')}</span><span class="count">${wolCount}</span></button>`,
    `<button type="button" class="filter-chip filter-pinned ${accessFilter === 'pinned' ? 'active' : ''}" data-access="pinned"><span class="chip-label">${t('filter.pinned')}<span class="chip-icon chip-icon-star" aria-hidden="true">★</span></span><span class="count">${pinnedCount}</span></button>`,
  ].join('');
  container.querySelectorAll('.filter-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      accessFilter = chip.dataset.access;
      if (accessFilter === 'all') availabilityFilter = 'all';
      guardLayoutWidth('access filter', () => renderServices());
    });
  });
}

function renderAvailabilityFilters() {
  const container = $('#availability-filters');
  if (!container) return;

  const allCount = applyServiceFilters(services, { availability: 'all' }).length;
  const onlineCount = applyServiceFilters(services, { availability: 'online' }).length;
  const offlineCount = applyServiceFilters(services, { availability: 'offline' }).length;

  container.innerHTML = [
    `<button type="button" class="filter-chip filter-all ${availabilityFilter === 'all' ? 'active' : ''}" data-availability="all"><span class="chip-label">${t('filter.all')}</span><span class="count">${allCount}</span></button>`,
    `<button type="button" class="filter-chip filter-online ${availabilityFilter === 'online' ? 'active' : ''}" data-availability="online"><span class="chip-label"><span class="chip-dot chip-dot-online" aria-hidden="true"></span>${t('filter.online')}</span><span class="count">${onlineCount}</span></button>`,
    `<button type="button" class="filter-chip filter-offline ${availabilityFilter === 'offline' ? 'active' : ''}" data-availability="offline"><span class="chip-label"><span class="chip-dot chip-dot-offline" aria-hidden="true"></span>${t('filter.offline')}</span><span class="count">${offlineCount}</span></button>`,
  ].join('');
  container.querySelectorAll('.filter-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      availabilityFilter = chip.dataset.availability;
      guardLayoutWidth('availability filter', () => renderServices());
    });
  });
}

function renderFilters() {
  const base = applyServiceFilters(services, { category: 'all' });
  const cats = {};
  base.forEach((s) => {
    cats[s.category] = (cats[s.category] || 0) + 1;
  });

  const container = $('#category-filters');
  const allCount = applyServiceFilters(services, { category: 'all' }).length;
  const chips = [
    `<button type="button" class="filter-chip ${activeFilter === 'all' ? 'active' : ''}" data-cat="all"><span class="chip-label">${t('filter.all')}</span><span class="count">${allCount}</span></button>`,
  ];
  Object.entries(cats)
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([cat]) => {
      const count = applyServiceFilters(services, { category: cat }).length;
      chips.push(
        `<button type="button" class="filter-chip ${activeFilter === cat ? 'active' : ''}" data-cat="${cat}"><span class="chip-label">${cat}</span><span class="count">${count}</span></button>`
      );
    });
  container.innerHTML = chips.join('');
  container.querySelectorAll('.filter-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      activeFilter = chip.dataset.cat;
      guardLayoutWidth('category filter', () => renderServices());
    });
  });
}

function renderNetworkFilters() {
  const container = $('#network-filters');
  if (!container) return;

  const accessSearchBase = filterBySearch(filterByAccess(services));
  const counts = collectNetworkSubnets(accessSearchBase);
  const subnets = Object.keys(counts);

  if (networkFilter !== 'all' && !applyServiceFilters(services, { network: networkFilter }).length) {
    networkFilter = 'all';
  }

  if (subnets.length <= 1) {
    container.classList.add('hidden');
    container.innerHTML = '';
    return;
  }

  container.classList.remove('hidden');
  const localSubnet = getLocalNetworkSubnet();
  const sorted = subnets.sort((a, b) => {
    if (a === localSubnet) return -1;
    if (b === localSubnet) return 1;
    return a.localeCompare(b);
  });
  const allNetworksCount = applyServiceFilters(services, { network: 'all' }).length;

  const chips = [
    `<button type="button" class="filter-chip network ${networkFilter === 'all' ? 'active' : ''}" data-network="all"><span class="chip-label">${t('filter.allNetworks')}</span><span class="count">${allNetworksCount}</span></button>`,
  ];
  sorted.forEach((subnet) => {
    const isLocal = subnet === localSubnet;
    const count = applyServiceFilters(services, { network: subnet }).length;
    chips.push(
      `<button type="button" class="filter-chip network ${isLocal ? 'network-local' : ''} ${networkFilter === subnet ? 'active' : ''}" data-network="${esc(subnet)}"><span class="chip-label">${esc(subnet)}</span><span class="count">${count}</span></button>`
    );
  });
  container.innerHTML = chips.join('');
  container.querySelectorAll('.filter-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      networkFilter = chip.dataset.network;
      guardLayoutWidth('network filter', () => renderServices());
    });
  });
}

function formatRelativeTime(iso) {
  const d = parseISODate(iso);
  if (!d) return '';
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return t('status.justNow');
  if (mins < 60) return t('status.minutesAgo', { count: mins });
  const hours = Math.floor(mins / 60);
  if (hours < 48) return t('status.hoursAgo', { count: hours });
  const days = Math.floor(hours / 24);
  return t('status.daysAgo', { count: days });
}

function statusTooltip(s) {
  const state = serviceHealthState(s);
  if (state === 'online') return t('status.online');
  if (state === 'error') return serviceHealthError(s) || t('status.error');
  if (state === 'stale') return t('status.stale');
  if (state === 'unknown') return t('status.unknown');
  const since = formatRelativeTime(s.last_seen);
  return since ? t('status.offlineSince', { time: since }) : t('status.offline');
}

function serviceIsOffline(s) {
  return serviceAvailabilityBucket(s) === 'offline';
}

function serviceIsOnlineHealthy(s) {
  return serviceAvailabilityBucket(s) === 'online';
}

function serviceHealthState(s) {
  if (hasServiceHealthWarning(s)) return 'error';
  if (s.is_online === false) return 'offline';
  if (s.is_online === true) return 'online';
  if (!s.last_checked) {
    return appSettings.health_check_enabled !== false ? 'unknown' : 'online';
  }
  const intervalSec = Math.max(15, Math.min(900, appSettings.health_check_interval || 60));
  const ageMs = Date.now() - new Date(s.last_checked).getTime();
  if (ageMs > intervalSec * 1000 * 3) return 'stale';
  return 'unknown';
}

function serviceUptimeLabel(s) {
  const state = serviceHealthState(s);
  if (state === 'online') {
    if (s.last_checked) {
      const intervalSec = Math.max(15, Math.min(900, appSettings.health_check_interval || 60));
      const ageMs = Date.now() - new Date(s.last_checked).getTime();
      if (ageMs > intervalSec * 1000 * 2) return '';
      const rel = formatRelativeTime(s.last_checked);
      return rel ? t('status.checkedAgo', { time: rel }) : '';
    }
    return '';
  }
  if (state === 'offline' && s.last_seen) {
    const rel = formatRelativeTime(s.last_seen);
    return rel ? t('status.lastSeen', { time: rel }) : '';
  }
  if (state === 'stale' && s.last_checked) {
    const rel = formatRelativeTime(s.last_checked);
    return rel ? t('status.checkedAgo', { time: rel }) : t('status.stale');
  }
  if (state === 'unknown') return t('status.unknown');
  return '';
}

function isHttpErrorName(name) {
  if (!name) return false;
  const n = String(name).trim().toLowerCase();
  if (/^\d{3}[\s:.\-]/.test(n)) return true;
  return /\b(authorization\s+required|unauthorized|forbidden|not\s+found|bad\s+request)\b/.test(n);
}

function displayServiceName(s) {
  if (!isHttpErrorName(s.name)) return s.name;
  if (s.host && s.port) return `${s.host}:${s.port}`;
  if (s.host) return s.host;
  if (s.port) return `Service :${s.port}`;
  return t('badge.error');
}

function serviceHealthError(s) {
  if (s.health_detail) return s.health_detail;
  if (isHttpErrorName(s.name)) return s.name;
  return '';
}

function serviceHealthBadge(s) {
  const err = serviceHealthError(s);
  if (!err) return '';
  const code = err.match(/^(\d{3})\b/);
  return code ? code[1] : t('badge.error');
}

function isReachableHttpDetail(detail) {
  if (!detail) return false;
  const d = String(detail).trim();
  return /^(?:HTTP\s+)?(?:30[0-9]|401|403)\b/i.test(d)
    || /\b(authorization\s+required|unauthorized|forbidden)\b/i.test(d);
}

function hasServiceHealthWarning(s) {
  const detail = s.health_detail || '';
  if (/^(?:HTTP\s+)?5\d{2}\b/i.test(detail)) return true;
  if (isReachableHttpDetail(detail)) return false;
  if (detail) return true;
  return s.is_online === false && isHttpErrorName(s.name);
}

function sanitizeServiceUrl(url) {
  if (!url || url === '#') return url || '';
  let text = String(url);
  try {
    text = decodeURIComponent(text);
  } catch {
    /* keep raw url when not percent-encoded */
  }
  return text
    .replace(/\?b'([^']*)'/g, '?$1')
    .replace(/\?b"([^"]*)"/g, '?$1')
    .replace(/b'([^']*)'/g, '$1')
    .replace(/b"([^"]*)"/g, '$1');
}

function formatServiceUrlDisplay(url) {
  const full = sanitizeServiceUrl(url);
  if (!full || full === '#') return { display: full, full };
  try {
    const u = new URL(full);
    const base = `${u.protocol}//${u.host}${u.pathname}`;
    if (u.search && u.search.length > 24) {
      return { display: base, full };
    }
    return { display: full.replace(/\/$/, '') || full, full };
  } catch {
    const q = full.indexOf('?');
    if (q > 0 && full.length - q > 24) {
      return { display: full.slice(0, q), full };
    }
    return { display: full, full };
  }
}

function pinnedHoverActionsHtml(s) {
  const hasNotes = !!(s.service_notes && s.service_notes.trim());
  const canPower = isWolDevice(s);
  return `
        <button type="button" class="service-action service-edit-btn" data-id="${s.id}" title="${t('action.edit')}">✎</button>
        <button type="button" class="service-action service-notes-btn ${hasNotes ? 'has-content' : ''}" data-id="${s.id}" title="${t('modal.serviceNotes')}">📝</button>
        <button type="button" class="service-action service-wol-btn ${canPower ? '' : 'is-placeholder'}" data-id="${s.id}" title="${t('action.wol')}" ${canPower ? '' : 'tabindex="-1" aria-hidden="true"'}>⚡</button>
        <button type="button" class="service-action service-sleep-btn ${canPower && isServiceOnline(s) ? '' : 'is-placeholder'}" data-id="${s.id}" title="${t('action.sleep')}" ${canPower && isServiceOnline(s) ? '' : 'tabindex="-1" aria-hidden="true"'}>💤</button>`;
}

function pinnedChipActionsHtml(s) {
  const hasNotes = !!(s.service_notes && s.service_notes.trim());
  const canPower = isWolDevice(s);
  return `
        <button type="button" class="pinned-chip-action pinned-chip-edit" data-id="${s.id}" title="${t('action.edit')}">✎</button>
        <button type="button" class="pinned-chip-action pinned-chip-notes ${hasNotes ? 'has-content' : ''}" data-id="${s.id}" title="${t('modal.serviceNotes')}">📝</button>
        <button type="button" class="pinned-chip-action pinned-chip-wol ${canPower ? '' : 'is-placeholder'}" data-id="${s.id}" title="${t('action.wol')}" ${canPower ? '' : 'tabindex="-1" aria-hidden="true"'}>⚡</button>
        <button type="button" class="pinned-chip-action pinned-chip-sleep ${canPower && isServiceOnline(s) ? '' : 'is-placeholder'}" data-id="${s.id}" title="${t('action.sleep')}" ${canPower && isServiceOnline(s) ? '' : 'tabindex="-1" aria-hidden="true"'}>💤</button>`;
}

function serviceCardHtml(s, opts = {}) {
  const { context = 'services', pinnedLayout = dashboardLayout() } = opts;
  const isPinnedCard = context === 'pinned';
  const isPinnedClassic = isPinnedCard && isPinnedClassicLayout(pinnedLayout);
  const isPinnedMedium = isPinnedCard && pinnedLayout === 'medium';
  const compact = !isPinnedCard && appSettings.card_style === 'compact';
  const isHostOnly = s.protocol === 'host' || s.port === 0;
  const showUrl = isPinnedCard
    ? (isPinnedClassic && appSettings.show_service_urls !== false)
    : (appSettings.show_service_urls !== false);
  const showPort = appSettings.show_ports !== false && !isHostOnly;
  const showMeta = isPinnedCard
    ? (isPinnedClassic ? (showPort || showUrl) : showPort)
    : (!compact || showPort || (showUrl && isHostOnly));
  const offline = s.is_online === false;
  const hasNotes = !!(s.service_notes && s.service_notes.trim());
  const canPower = isWolDevice(s);
  const powerContext = accessFilter === 'wol';
  const cardUrl = isHostOnly ? '' : sanitizeServiceUrl(s.url);
  const urlInfo = isHostOnly ? { display: s.host, full: s.host } : formatServiceUrlDisplay(s.url);
  const pinTitle = s.pinned ? t('action.unpin') : t('action.pin');
  const healthErr = serviceHealthError(s);
  const hasAuthError = hasServiceHealthWarning(s);
  const healthBadge = serviceHealthBadge(s);
  const healthState = serviceHealthState(s);
  const accent = categoryAccentColor(s.category);
  const uptimeLabel = serviceUptimeLabel(s);
  const displayName = displayServiceName(s);
  const pinnedNameTitle = isPinnedCard && urlInfo.full
    ? `${displayName} — ${urlInfo.full}`
    : displayName;
  const showPinnedBadges = !isPinnedCard || isPinnedClassic;
  return `
    <div class="service-card ${isPinnedCard ? 'service-card--pinned' : ''} ${isPinnedMedium ? 'service-card--pinned-medium' : ''} ${compact ? 'service-card--compact' : ''} ${s.pinned ? 'pinned' : ''} ${s.has_login ? 'has-login' : ''} ${offline ? 'is-offline' : ''} ${hasAuthError ? 'has-auth-error' : ''} ${isHostOnly ? 'host-only' : ''} ${powerContext ? 'power-context' : ''}" data-id="${s.id}" data-url="${esc(cardUrl)}" style="--category-accent:${accent}">
      ${renderServiceWatermark(s)}
      ${!isPinnedCard ? `<button type="button" class="service-delete" data-id="${s.id}" title="${t('modal.delete')}" aria-label="${t('modal.delete')}">&times;</button>` : ''}
      ${isPinnedMedium ? `
      <div class="pinned-medium-toolbar" aria-hidden="true">
        <button type="button" class="pinned-medium-unpin service-action service-pin-btn is-pinned" data-id="${s.id}" title="${pinTitle}" aria-label="${pinTitle}" aria-pressed="true">★</button>
        <div class="pinned-medium-actions">${pinnedHoverActionsHtml(s)}</div>
      </div>` : ''}
      ${isPinnedCard && !isPinnedMedium ? `<button type="button" class="pinned-unpin-btn service-action service-pin-btn is-pinned" data-id="${s.id}" title="${pinTitle}" aria-label="${pinTitle}" aria-pressed="true">★</button>` : ''}
      <div class="service-top">
        <div class="service-badges">
          ${hasAuthError && showPinnedBadges ? `<span class="badge badge-error service-error-badge" title="${esc(healthErr)}">${esc(healthBadge)}</span>` : ''}
          ${s.has_login && showPinnedBadges ? `<span class="badge badge-login">${t('badge.login')}</span>` : ''}
          ${showPinnedBadges && (!compact || isPinnedClassic) && s.auto_discovered ? `<span class="badge badge-auto">${t('badge.auto')}</span>` : ''}
          ${s.pinned && !isPinnedCard ? `<span class="badge badge-pin">${t('badge.pin')}</span>` : ''}
          ${offline && showPinnedBadges ? `<span class="badge badge-offline">${t('badge.offline')}</span>` : ''}
        </div>
        <div class="service-icon-wrap">
          ${renderServiceIcon(s)}
          <span class="status-dot status-${healthState}" title="${esc(statusTooltip(s))}"></span>
        </div>
      </div>
      <div class="service-body">
        <div class="service-name" title="${esc(pinnedNameTitle)}">${esc(displayName)}</div>
        ${showUrl ? `<div class="service-url ${isHostOnly ? 'service-url--host' : ''}" title="${esc(urlInfo.full)}">${esc(urlInfo.display)}</div>` : ''}
        ${showMeta ? `<div class="service-meta">
          ${(!compact && !isPinnedCard) || isPinnedClassic ? `<span class="service-category" title="${esc(s.category)}">${esc(s.category)}</span>` : ''}
          ${showPort ? `<span class="service-port">:${s.port}</span>` : ''}
        </div>` : ''}
        ${uptimeLabel && (isPinnedClassic || !isPinnedCard) ? `<div class="service-uptime" aria-hidden="true">${esc(uptimeLabel)}</div>` : ''}
      </div>
      ${isPinnedCard && !isPinnedMedium ? `<div class="service-actions service-actions--pinned">${pinnedHoverActionsHtml(s)}</div>` : !isPinnedCard ? `<div class="service-actions ${powerContext ? 'service-actions--power' : ''}">
        ${context === 'services' ? `<button type="button" class="service-action service-edit-btn" data-id="${s.id}" title="${t('action.edit')}">✎</button>` : ''}
        <button type="button" class="service-action service-pin-btn ${s.pinned ? 'is-pinned' : ''}" data-id="${s.id}" title="${pinTitle}" aria-pressed="${s.pinned ? 'true' : 'false'}">★</button>
        <button type="button" class="service-action service-notes-btn ${hasNotes ? 'has-content' : ''}" data-id="${s.id}" title="${t('modal.serviceNotes')}">📝</button>
        <button type="button" class="service-action service-wol-btn ${canPower ? '' : 'is-placeholder'}" data-id="${s.id}" title="${t('action.wol')}" ${canPower ? '' : 'tabindex="-1" aria-hidden="true"'}>⚡</button>
        <button type="button" class="service-action service-sleep-btn ${canPower && isServiceOnline(s) ? '' : 'is-placeholder'}" data-id="${s.id}" title="${t('action.sleep')}" ${canPower && isServiceOnline(s) ? '' : 'tabindex="-1" aria-hidden="true"'}>💤</button>
      </div>` : ''}
    </div>`;
}

function bindServiceCards(root) {
  bindServiceDeletes(root);
  root.querySelectorAll('.service-card').forEach((card) => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('.service-delete, .service-action, .service-edit-btn')) return;
      const url = card.dataset.url;
      if (url && url !== '#') window.open(url, '_blank', 'noopener');
    });
  });
  root.querySelectorAll('.service-edit-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openServiceEditModal(Number(btn.dataset.id));
    });
  });
  root.querySelectorAll('.service-pin-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await toggleServicePin(Number(btn.dataset.id));
    });
  });
  root.querySelectorAll('.service-notes-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openServiceNotesModal(Number(btn.dataset.id));
    });
  });
  root.querySelectorAll('.service-wol-btn:not(.is-placeholder)').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await api(`/api/services/${btn.dataset.id}/wol`, { method: 'POST' });
        showToast(t('toast.wolSent'), 'success');
      } catch (err) {
        showToast(err.message || t('action.wolFailed'), 'error');
      }
    });
  });
  root.querySelectorAll('.service-sleep-btn:not(.is-placeholder)').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm(t('confirm.sleep'))) return;
      try {
        await api(`/api/services/${btn.dataset.id}/sleep`, { method: 'POST' });
        showToast(t('toast.sleepSent'), 'success');
        await loadDashboard();
      } catch (err) {
        showToast(err.message || t('action.sleepFailed'), 'error');
      }
    });
  });
}

let serviceNotesMacAuto = false;

function updateServiceNotesMacHint(state, message) {
  const hint = $('#service-notes-mac-hint');
  if (!hint) return;
  if (state === 'loading') {
    hint.textContent = t('modal.macDetecting');
    hint.className = 'hint mac-hint-loading';
  } else if (state === 'auto') {
    hint.textContent = t('modal.macAutoDetected');
    hint.className = 'hint mac-hint-auto';
  } else if (state === 'manual') {
    hint.textContent = t('modal.macManual');
    hint.className = 'hint';
  } else if (state === 'notfound') {
    hint.textContent = t('modal.macNotFound');
    hint.className = 'hint mac-hint-error';
  } else if (state === 'apierror') {
    hint.textContent = message || t('modal.macDetectFailed');
    hint.className = 'hint mac-hint-api-error';
  } else {
    hint.textContent = t('settings.arpScan.modalHint');
    hint.className = 'hint';
  }
}

function updateServiceNotesPortHints(svc) {
  const wolHint = $('#service-notes-wol-port-hint');
  const solHint = $('#service-notes-sol-port-hint');
  const defaultWol = appSettings.wol_port ?? 9;
  const defaultSol = appSettings.sol_port ?? appSettings.wol_port ?? 9;
  if (wolHint) {
    wolHint.textContent = svc.wol_port == null ? t('modal.portFromSettings') : '';
  }
  if (solHint) {
    solHint.textContent = svc.sol_port == null ? t('modal.portFromSettings') : '';
  }
  return { defaultWol, defaultSol };
}

async function lookupServiceMac(serviceId, { auto = false } = {}) {
  const spinner = $('#service-notes-mac-loading');
  const macInput = $('#service-notes-mac');
  if (!macInput) return;
  spinner?.classList.remove('is-hidden');
  updateServiceNotesMacHint('loading');
  try {
    const result = await api(`/api/services/${serviceId}/network-info?ping=true`);
    if (result.found && result.mac) {
      macInput.value = result.mac;
      serviceNotesMacAuto = true;
      updateServiceNotesMacHint('auto');
      if (auto) await loadServices();
    } else {
      serviceNotesMacAuto = false;
      updateServiceNotesMacHint('notfound');
    }
  } catch (err) {
    serviceNotesMacAuto = false;
    const msg = err.message || t('modal.macDetectFailed');
    updateServiceNotesMacHint(auto ? 'notfound' : 'apierror', msg);
  } finally {
    spinner?.classList.add('is-hidden');
  }
}

function openServiceNotesModal(id) {
  const svc = services.find((s) => s.id === id);
  if (!svc) return;
  $('#service-notes-id').value = id;
  $('#service-notes-title').textContent = `${t('modal.serviceNotes')}: ${svc.name}`;
  $('#service-notes-text').value = svc.service_notes || '';
  $('#service-notes-mac').value = svc.mac_address || '';
  serviceNotesMacAuto = false;
  $('#service-notes-wol').checked = !!svc.wol_enabled;
  const { defaultWol, defaultSol } = updateServiceNotesPortHints(svc);
  $('#service-notes-wol-port').value = svc.wol_port ?? String(defaultWol);
  $('#service-notes-wol-port').placeholder = String(defaultWol);
  $('#service-notes-sol-port').value = svc.sol_port ?? String(defaultSol);
  $('#service-notes-sol-port').placeholder = String(defaultSol);
  $('#service-notes-broadcast').value = svc.broadcast_ip || '';
  $('#service-notes-broadcast').placeholder = appSettings.wol_broadcast_ip || '255.255.255.255';
  if (svc.mac_address) {
    updateServiceNotesMacHint('saved');
  } else {
    updateServiceNotesMacHint('manual');
    lookupServiceMac(id, { auto: true });
  }
  openModal('service-notes-modal');
}

function renderPowerDevicesList() {
  const list = $('#power-devices-list');
  const select = $('#power-link-service');
  if (!list || !select) return;
  const powered = services.filter((s) => s.mac_address);
  list.innerHTML = powered.length
    ? powered.map((s) => `<div class="power-device-row"><span>${esc(s.name)}</span><code>${esc(s.mac_address)}</code><span class="${s.wol_enabled ? 'on' : 'off'}">${s.wol_enabled ? t('settings.powerOn') : t('settings.powerOff')}</span></div>`).join('')
    : `<p class="hint">${t('settings.powerDevicesEmpty')}</p>`;
  select.innerHTML = services.map((s) => `<option value="${s.id}">${esc(s.name)} (${esc(s.host)})</option>`).join('');
}

function bindServiceDeletes(root) {
  root.querySelectorAll('.service-delete').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!confirm(t('confirm.delete.service'))) return;
      await api(`/api/services/${btn.dataset.id}`, { method: 'DELETE' });
      await loadDashboard();
    });
  });
}

function getIconClass(icon) {
  const safe = (icon || 'globe').toLowerCase().replace(/[^a-z0-9]/g, '');
  return `icon-${safe}`;
}

function renderServiceIcon(s) {
  if (s.icon_url) {
    const fallback = getIconClass(s.icon);
    return `<div class="service-icon service-icon-brand" data-fallback="${fallback}">
      <img src="${esc(s.icon_url)}" alt="" loading="lazy" referrerpolicy="no-referrer"
        onerror="const p=this.parentElement;p.className='service-icon '+p.dataset.fallback;p.textContent='';" />
    </div>`;
  }
  return `<div class="service-icon ${getIconClass(s.icon)}"></div>`;
}

function populateServiceCategorySuggestions() {
  const datalist = $('#service-category-suggestions');
  if (!datalist) return;
  const cats = new Set(DEFAULT_SERVICE_CATEGORIES);
  services.forEach((s) => {
    if (s.category) cats.add(s.category);
  });
  datalist.innerHTML = [...cats].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
    .map((cat) => `<option value="${esc(cat)}"></option>`).join('');
}

function serviceIconPrefixFromInputId(selectId = 'edit-icon') {
  return selectId.replace(/-icon$/, '');
}

function getRecentIcons() {
  try {
    const raw = localStorage.getItem(RECENT_ICONS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter((i) => typeof i === 'string' && SERVICE_ICON_PRESETS.includes(i))
      : [];
  } catch {
    return [];
  }
}

function pushRecentIcon(icon) {
  const safe = (icon || 'globe').toLowerCase().replace(/[^a-z0-9]/g, '') || 'globe';
  if (!SERVICE_ICON_PRESETS.includes(safe)) return;
  let recent = getRecentIcons().filter((i) => i !== safe);
  recent.unshift(safe);
  localStorage.setItem(RECENT_ICONS_KEY, JSON.stringify(recent.slice(0, MAX_RECENT_ICONS)));
}

function iconsForPickerGroup(groupId) {
  if (groupId === 'recent') return getRecentIcons();
  if (groupId === 'all') return [...SERVICE_ICON_PRESETS];
  const group = SERVICE_ICON_GROUPS.find((g) => g.id === groupId);
  if (!group?.icons) return [...SERVICE_ICON_PRESETS];
  return group.icons.filter((icon) => SERVICE_ICON_PRESETS.includes(icon));
}

function filteredServiceIcons(prefix) {
  const state = iconPickerState[prefix] || { group: 'all', query: '' };
  const q = (state.query || '').trim().toLowerCase();
  let icons = iconsForPickerGroup(state.group);
  if (q) icons = icons.filter((icon) => icon.includes(q));
  const current = ($(`#${prefix}-icon`)?.value || 'globe').toLowerCase();
  if (current && !icons.includes(current)) icons = [current, ...icons];
  return icons;
}

function refreshIconPickerTabs(prefix) {
  const recent = getRecentIcons();
  if (iconPickerState[prefix]?.group === 'recent' && recent.length === 0) {
    iconPickerState[prefix].group = 'all';
  }
  const group = iconPickerState[prefix]?.group || 'all';
  const host = $(`#${prefix}-icon-picker`);
  if (!host) return;
  host.querySelectorAll('.icon-picker-tab').forEach((tab) => {
    if (tab.dataset.group === 'recent') {
      tab.classList.toggle('hidden', recent.length === 0);
    }
    const active = tab.dataset.group === group;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', active ? 'true' : 'false');
  });
}

function refreshIconPickerGrid(prefix) {
  const grid = $(`#${prefix}-icon-grid`);
  const empty = $(`#${prefix}-icon-empty`);
  if (!grid) return;
  const selected = ($(`#${prefix}-icon`)?.value || 'globe').toLowerCase();
  const icons = filteredServiceIcons(prefix);
  if (empty) empty.classList.toggle('hidden', icons.length > 0);
  grid.innerHTML = icons.map((icon) => {
    const label = icon.charAt(0).toUpperCase() + icon.slice(1);
    const isSelected = icon === selected;
    return `<button type="button" class="icon-picker-tile${isSelected ? ' selected' : ''}" role="option"
      aria-selected="${isSelected}" data-icon="${esc(icon)}" title="${esc(label)}">
      <div class="service-icon ${getIconClass(icon)}"></div>
      <span class="icon-picker-tile-label">${esc(label)}</span>
    </button>`;
  }).join('');
}

function bindIconPickerGridKeyboard(prefix) {
  const grid = $(`#${prefix}-icon-grid`);
  if (!grid || grid.dataset.keybound === '1') return;
  grid.dataset.keybound = '1';
  grid.addEventListener('keydown', (e) => {
    const tiles = [...grid.querySelectorAll('.icon-picker-tile')];
    if (!tiles.length) return;
    const current = document.activeElement?.closest?.('.icon-picker-tile');
    let idx = current ? tiles.indexOf(current) : -1;
    const cols = Math.max(1, Math.floor(grid.clientWidth / 56) || 4);
    if (e.key === 'ArrowRight') { e.preventDefault(); idx = Math.min(tiles.length - 1, idx + 1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); idx = Math.max(0, idx <= 0 ? 0 : idx - 1); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); idx = Math.min(tiles.length - 1, idx < 0 ? 0 : idx + cols); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); idx = Math.max(0, idx < 0 ? 0 : idx - cols); }
    else if (e.key === 'Enter' || e.key === ' ') {
      if (current) { e.preventDefault(); selectServiceIcon(prefix, current.dataset.icon); }
      return;
    } else return;
    tiles[idx]?.focus();
  });
}

function buildIconPicker(prefix) {
  const host = $(`#${prefix}-icon-picker`);
  if (!host || host.dataset.ready === '1') return;
  host.dataset.ready = '1';
  host.innerHTML = `
    <div class="icon-picker">
      <div class="icon-picker-toolbar">
        <input type="search" class="icon-picker-search" id="${prefix}-icon-search"
          data-i18n-placeholder="modal.edit.iconSearch" autocomplete="off"
          aria-label="${esc(t('modal.edit.iconSearch'))}" />
        <div class="icon-picker-tabs" role="tablist" aria-label="${esc(t('modal.edit.iconPreset'))}">
          ${SERVICE_ICON_GROUPS.map((g) =>
            `<button type="button" class="icon-picker-tab${g.id === 'recent' ? ' hidden' : ''}" role="tab" data-group="${g.id}" data-i18n="${g.labelKey}"></button>`,
          ).join('')}
        </div>
      </div>
      <div class="icon-picker-grid" id="${prefix}-icon-grid" role="listbox" tabindex="0"
        aria-label="${esc(t('modal.edit.iconPickAria'))}"></div>
      <p class="icon-picker-empty hidden" id="${prefix}-icon-empty" data-i18n="modal.edit.iconEmpty"></p>
    </div>`;

  host.querySelector('.icon-picker-search')?.addEventListener('input', (e) => {
    iconPickerState[prefix].query = e.target.value;
    refreshIconPickerGrid(prefix);
  });
  host.querySelectorAll('.icon-picker-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      iconPickerState[prefix].group = tab.dataset.group || 'all';
      refreshIconPickerTabs(prefix);
      refreshIconPickerGrid(prefix);
    });
  });
  host.addEventListener('click', (e) => {
    const tile = e.target.closest('.icon-picker-tile');
    if (!tile) return;
    selectServiceIcon(prefix, tile.dataset.icon);
  });
  bindIconPickerGridKeyboard(prefix);
  applyI18n();
  refreshIconPickerTabs(prefix);
  refreshIconPickerGrid(prefix);
}

function selectServiceIcon(prefix, icon) {
  setServiceIconValue(prefix, icon, { trackRecent: true });
}

function setServiceIconValue(prefix, icon, { trackRecent = false } = {}) {
  const safe = (icon || 'globe').toLowerCase().replace(/[^a-z0-9]/g, '') || 'globe';
  const input = $(`#${prefix}-icon`);
  if (input) input.value = safe;
  if (trackRecent) pushRecentIcon(safe);
  refreshIconPickerTabs(prefix);
  refreshIconPickerGrid(prefix);
  updateServiceIconPreview(prefix);
  input?.dispatchEvent(new Event('change', { bubbles: true }));
}

function populateServiceIconSelect(selected = 'globe', selectId = 'edit-icon') {
  setServiceIconValue(serviceIconPrefixFromInputId(selectId), selected);
}

function initServiceIconPickers() {
  ['edit', 'add'].forEach((prefix) => {
    buildIconPicker(prefix);
    setupServiceIconUpload(prefix);
  });
}

function isUploadedIconUrl(url) {
  return (url || '').trim().startsWith('/uploads/icons/');
}

function syncIconUrlDetails(prefix) {
  const details = $(`#${prefix}-icon-url-details`);
  if (!details) return;
  const iconUrl = $(`#${prefix}-icon-url`)?.value.trim() || '';
  details.open = !!iconUrl && !isUploadedIconUrl(iconUrl);
}

function updateServiceIconPreview(prefix) {
  const preview = $(`#${prefix}-icon-preview`);
  if (!preview) return;
  const icon = $(`#${prefix}-icon`)?.value || 'globe';
  const iconUrl = $(`#${prefix}-icon-url`)?.value.trim() || '';
  preview.innerHTML = renderServiceIcon({ icon, icon_url: iconUrl || null });
  refreshIconUploadStatus(prefix);
  syncIconUrlDetails(prefix);
}

function refreshIconUploadStatus(prefix) {
  const status = $(`#${prefix}-icon-upload-status`);
  if (!status) return;
  const iconUrl = $(`#${prefix}-icon-url`)?.value.trim() || '';
  if (!isUploadedIconUrl(iconUrl)) {
    status.classList.add('hidden');
    status.innerHTML = '';
    return;
  }
  const filename = iconUrl.split('/').pop() || iconUrl;
  status.classList.remove('hidden');
  status.innerHTML = `
    <img class="icon-upload-thumb" src="${esc(iconUrl)}" alt="" loading="lazy" />
    <span class="icon-upload-name" title="${esc(filename)}">${esc(filename)}</span>`;
}

function isAllowedIconFile(file) {
  if (!file) return false;
  const mime = (file.type || '').toLowerCase();
  if (mime && ALLOWED_ICON_MIMES.has(mime)) return true;
  const ext = file.name.split('.').pop()?.toLowerCase();
  return ext === 'svg' || ext === 'png' || ext === 'jpg' || ext === 'jpeg' || ext === 'webp';
}

async function uploadServiceIcon(prefix, file) {
  if (!file) return;
  const btn = $(`#${prefix}-icon-upload-btn`);
  if (!isAllowedIconFile(file)) {
    showToast(t('modal.edit.uploadFailed'), 'error');
    return;
  }
  if (file.size > MAX_ICON_UPLOAD_BYTES) {
    showToast(t('modal.edit.uploadTooLarge'), 'error');
    return;
  }
  if (btn) btn.disabled = true;
  try {
    const form = new FormData();
    form.append('file', file);
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${API}/api/services/upload-icon`, {
      method: 'POST',
      headers,
      body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(translateApiDetail(data.detail) || t('modal.edit.uploadFailed'));
    }
    const urlInput = $(`#${prefix}-icon-url`);
    if (urlInput) {
      urlInput.value = data.url;
      urlInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    updateServiceIconPreview(prefix);
    showToast(file.name, 'success');
  } catch (err) {
    showToast(err.message || t('modal.edit.uploadFailed'), 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function bindFileUploadButton(btn, fileInput, onFile) {
  if (!btn || !fileInput || btn.dataset.uploadBound) return;
  btn.dataset.uploadBound = '1';
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (btn.disabled) return;
    fileInput.click();
  });
  fileInput.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (file) await onFile(file);
    e.target.value = '';
  });
}

function setupServiceIconUpload(prefix) {
  bindFileUploadButton(
    $(`#${prefix}-icon-upload-btn`),
    $(`#${prefix}-icon-file`),
    (file) => uploadServiceIcon(prefix, file),
  );
}

function refreshSettingsFaviconStatus() {
  const status = $('#settings-favicon-upload-status');
  if (!status) return;
  const iconUrl = $('#settings-favicon')?.value.trim() || '';
  if (!isUploadedIconUrl(iconUrl)) {
    status.classList.add('hidden');
    status.innerHTML = '';
    return;
  }
  const filename = iconUrl.split('/').pop() || iconUrl;
  status.classList.remove('hidden');
  status.innerHTML = `
    <img class="icon-upload-thumb" src="${esc(iconUrl)}" alt="" loading="lazy" />
    <span class="icon-upload-name" title="${esc(filename)}">${esc(filename)}</span>`;
}

function syncSettingsFaviconDetails() {
  const details = $('#settings-favicon-url-details');
  if (!details) return;
  const iconUrl = $('#settings-favicon')?.value.trim() || '';
  details.open = !!iconUrl && !isUploadedIconUrl(iconUrl);
}

async function uploadSettingsFavicon(file) {
  if (!file) return;
  const btn = $('#settings-favicon-upload-btn');
  if (!isAllowedIconFile(file)) {
    showToast(t('modal.edit.uploadFailed'), 'error');
    return;
  }
  if (file.size > MAX_ICON_UPLOAD_BYTES) {
    showToast(t('modal.edit.uploadTooLarge'), 'error');
    return;
  }
  if (btn) btn.disabled = true;
  try {
    const form = new FormData();
    form.append('file', file);
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${API}/api/services/upload-icon`, {
      method: 'POST',
      headers,
      body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(translateApiDetail(data.detail) || t('modal.edit.uploadFailed'));
    }
    const urlInput = $('#settings-favicon');
    if (urlInput) urlInput.value = data.url;
    refreshSettingsFaviconStatus();
    syncSettingsFaviconDetails();
    applyFavicon(data.url);
    showToast(file.name, 'success');
  } catch (err) {
    showToast(err.message || t('modal.edit.uploadFailed'), 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function setupSettingsFaviconUpload() {
  bindFileUploadButton(
    $('#settings-favicon-upload-btn'),
    $('#settings-favicon-file'),
    uploadSettingsFavicon,
  );
  $('#settings-favicon')?.addEventListener('input', () => {
    refreshSettingsFaviconStatus();
    syncSettingsFaviconDetails();
  });
}

function updateEditServiceIconPreview() {
  updateServiceIconPreview('edit');
}

const LETTER_WATERMARK_ICONS = new Set(['nginx', 'apache', 'caddy', 'traefik']);

function serviceIconPreset(s) {
  return getIconClass((s.icon || 'globe').toLowerCase());
}

function watermarkFallbackHtml(s) {
  const icon = (s.icon || 'globe').toLowerCase();
  const cls = getIconClass(icon);
  if (LETTER_WATERMARK_ICONS.has(icon)) {
    return `<div class="service-card-watermark service-card-watermark--letter ${cls}" aria-hidden="true">${icon[0].toUpperCase()}</div>`;
  }
  if (icon && icon !== 'globe') {
    return `<div class="service-card-watermark ${cls}" aria-hidden="true"></div>`;
  }
  const letter = (s.name || '').trim().charAt(0);
  if (letter) {
    return `<div class="service-card-watermark service-card-watermark--letter" aria-hidden="true">${esc(letter.toUpperCase())}</div>`;
  }
  return netdashWatermarkHtml();
}

function netdashWatermarkHtml() {
  return `<div class="service-card-watermark service-card-watermark--img service-card-watermark--brand" aria-hidden="true"><img src="/static/favicon.svg" alt="" loading="eager" decoding="async" /></div>`;
}

function renderServiceWatermark(s) {
  const preset = serviceIconPreset(s);
  if (s.icon_url) {
    return `<div class="service-card-watermark service-card-watermark--img" data-preset="${preset}" aria-hidden="true"><img src="${esc(s.icon_url)}" alt="" loading="eager" decoding="async" referrerpolicy="no-referrer" onerror="const w=this.parentElement;w.classList.remove('service-card-watermark--img');w.classList.add(w.dataset.preset||'icon-globe');this.remove();" /></div>`;
  }
  return watermarkFallbackHtml(s);
}

function pinnedCategoryLabel(category) {
  const cat = (category || '').trim();
  return cat || t('modal.key.other');
}

function pinnedGroupSortKey(category) {
  const label = pinnedCategoryLabel(category);
  const idx = DEFAULT_SERVICE_CATEGORIES.indexOf(label);
  if (idx !== -1) return idx;
  return DEFAULT_SERVICE_CATEGORIES.length + label.toLowerCase();
}

function normalizeUrlCompareKey(url) {
  const clean = sanitizeServiceUrl(url).trim().toLowerCase();
  if (!clean) return '';
  try {
    const u = new URL(clean);
    const port = u.port || (u.protocol === 'https:' ? '443' : u.protocol === 'http:' ? '80' : '');
    const path = u.pathname.replace(/\/$/, '') || '/';
    return `${u.hostname}:${port}:${u.protocol}//${u.host}${path}${u.search}`;
  } catch {
    return clean.replace(/\/$/, '');
  }
}

function pinnedServiceDedupeKey(s) {
  if (s.protocol === 'host' || s.port === 0) {
    return `host:${(s.host || '').toLowerCase()}`;
  }
  const normalized = normalizeUrlCompareKey(s.url || '');
  if (normalized) return normalized;
  const host = (s.host || '').toLowerCase();
  const port = s.port ?? 0;
  return `${host}:${port}`;
}

function findDuplicateServicesByUrl(url, excludeId = null) {
  const key = normalizeUrlCompareKey(url);
  if (!key) return [];
  return services.filter((s) => {
    if (excludeId != null && s.id === excludeId) return false;
    if (s.protocol === 'host' || s.port === 0) return false;
    return normalizeUrlCompareKey(s.url || '') === key;
  });
}

function updateServiceUrlDuplicateHint(prefix, excludeId = null) {
  const input = $(`#${prefix}-url`);
  const hint = $(`#${prefix}-url-duplicate`);
  if (!input || !hint) return;
  const url = input.value.trim();
  const dupes = findDuplicateServicesByUrl(url, excludeId);
  if (!dupes.length) {
    hint.classList.add('hidden');
    hint.textContent = '';
    return;
  }
  const names = dupes.map((s) => s.name).join(', ');
  hint.textContent = t('modal.edit.duplicateUrl', { names });
  hint.classList.remove('hidden');
}

function dedupePinnedServices(list) {
  const seenUrl = new Set();
  const seenHostPort = new Set();
  return list.filter((s) => {
    const urlKey = pinnedServiceDedupeKey(s);
    if (seenUrl.has(urlKey)) return false;
    seenUrl.add(urlKey);
    if (s.protocol !== 'host' && s.port !== 0) {
      const hostPort = `${(s.host || '').toLowerCase()}:${s.port ?? 0}`;
      if (seenHostPort.has(hostPort)) return false;
      seenHostPort.add(hostPort);
    }
    return true;
  });
}

function groupPinnedServices(list) {
  const groups = new Map();
  list.forEach((s) => {
    const label = pinnedCategoryLabel(s.category);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(s);
  });
  return [...groups.entries()]
    .sort(([a], [b]) => {
      const ka = pinnedGroupSortKey(a);
      const kb = pinnedGroupSortKey(b);
      if (ka !== kb) return ka - kb;
      return a.localeCompare(b, undefined, { sensitivity: 'base' });
    })
    .map(([label, items]) => [
      label,
      items.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })),
    ]);
}

function pinnedChipHtml(s) {
  const isHostOnly = s.protocol === 'host' || s.port === 0;
  const showPort = appSettings.show_ports !== false && !isHostOnly;
  const offline = s.is_online === false;
  const cardUrl = isHostOnly ? '' : sanitizeServiceUrl(s.url);
  const urlInfo = isHostOnly ? { display: s.host, full: s.host } : formatServiceUrlDisplay(s.url);
  const displayName = displayServiceName(s);
  const tooltip = urlInfo.full ? `${displayName} — ${urlInfo.full}` : displayName;
  const healthState = serviceHealthState(s);
  const pinTitle = t('action.unpin');
  return `
    <div class="pinned-chip ${offline ? 'is-offline' : ''}" data-id="${s.id}" data-url="${esc(cardUrl)}" title="${esc(tooltip)}" style="--category-accent:${categoryAccentColor(s.category)}">
      <div class="pinned-chip-main">
        <div class="pinned-chip-icon-wrap">
          ${renderServiceIcon(s)}
          <span class="status-dot status-${healthState}" title="${esc(statusTooltip(s))}"></span>
        </div>
        <div class="pinned-chip-text">
          <span class="pinned-chip-name">${esc(displayName)}</span>
          ${showPort ? `<span class="pinned-chip-port" aria-hidden="true">:${s.port}</span>` : ''}
        </div>
      </div>
      <div class="pinned-chip-toolbar">
        <button type="button" class="pinned-chip-unpin-corner" data-id="${s.id}" title="${pinTitle}" aria-label="${pinTitle}">★</button>
        <div class="pinned-chip-actions">${pinnedChipActionsHtml(s)}</div>
      </div>
    </div>`;
}

function bindPinnedChips(root) {
  root.querySelectorAll('.pinned-chip').forEach((chip) => {
    chip.addEventListener('click', (e) => {
      if (e.target.closest('.pinned-chip-action, .pinned-chip-unpin-corner')) return;
      const url = chip.dataset.url;
      if (url && url !== '#') window.open(url, '_blank', 'noopener');
    });
  });
  root.querySelectorAll('.pinned-chip-unpin-corner').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await toggleServicePin(Number(btn.dataset.id));
    });
  });
  root.querySelectorAll('.pinned-chip-edit').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openServiceEditModal(Number(btn.dataset.id));
    });
  });
  root.querySelectorAll('.pinned-chip-notes').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openServiceNotesModal(Number(btn.dataset.id));
    });
  });
  root.querySelectorAll('.pinned-chip-wol:not(.is-placeholder)').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await api(`/api/services/${btn.dataset.id}/wol`, { method: 'POST' });
        showToast(t('toast.wolSent'), 'success');
      } catch (err) {
        showToast(err.message || t('action.wolFailed'), 'error');
      }
    });
  });
  root.querySelectorAll('.pinned-chip-sleep:not(.is-placeholder)').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm(t('confirm.sleep'))) return;
      try {
        await api(`/api/services/${btn.dataset.id}/sleep`, { method: 'POST' });
        showToast(t('toast.sleepSent'), 'success');
        await loadDashboard();
      } catch (err) {
        showToast(err.message || t('action.sleepFailed'), 'error');
      }
    });
  });
}

function updatePinnedSectionHeader(count) {
  const countEl = $('#pinned-section-count');
  if (!countEl) return;
  if (count > 0) {
    countEl.textContent = String(count);
    countEl.classList.remove('hidden');
  } else {
    countEl.textContent = '';
    countEl.classList.add('hidden');
  }
}

function renderPinnedServices() {
  const container = $('#pinned-container');
  const empty = $('#pinned-empty-state');
  if (!container) return;

  const pinned = dedupePinnedServices(services.filter((s) => s.pinned));
  const layout = dashboardLayout();
  updatePinnedSectionHeader(pinned.length);

  if (pinned.length === 0) {
    container.innerHTML = '';
    empty?.classList.remove('hidden');
    return;
  }

  empty?.classList.add('hidden');
  const groups = groupPinnedServices(pinned);

  if (layout === 'compact') {
    container.innerHTML = `
      <div class="pinned-groups pinned-groups--compact">
        ${groups.map(([label, items]) => `
          <section class="pinned-group pinned-group--compact">
            <h3 class="pinned-group-label" title="${esc(label)}">${esc(label)}</h3>
            <div class="pinned-chips">${items.map((s) => pinnedChipHtml(s)).join('')}</div>
          </section>
        `).join('')}
      </div>`;
    bindPinnedChips(container);
    return;
  }

  const gridClass = layout === 'medium' ? 'services-grid--pinned-medium' : 'services-grid--pinned';
  container.innerHTML = `
    <div class="pinned-groups pinned-groups--cards">
      ${groups.map(([label, items]) => `
        <section class="pinned-group pinned-group--cards">
          <h3 class="pinned-group-label" title="${esc(label)}">${esc(label)}</h3>
          <div class="services-grid ${gridClass}">${items.map((s) => serviceCardHtml(s, { context: 'pinned', pinnedLayout: layout })).join('')}</div>
        </section>
      `).join('')}
    </div>`;
  bindServiceCards(container);
}

async function toggleServicePin(id) {
  const svc = services.find((s) => s.id === id);
  if (!svc) return;
  const wasPinned = svc.pinned;
  const updated = await api(`/api/services/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ pinned: !svc.pinned }),
  });
  Object.assign(svc, normalizeService(updated));
  if (wasPinned) showToast(t('toast.unpinned'), 'success');
  updateStats();
  renderPinnedServices();
  if (currentPage === 'services') {
    patchServiceCardsForId(id);
  }
}

function patchServiceCardsForId(id) {
  const svc = services.find((s) => s.id === id);
  if (!svc) return;
  if (document.querySelector(`#pinned-container [data-id="${id}"]`)) {
    renderPinnedServices();
  }
  document.querySelectorAll(`.service-card[data-id="${id}"]`).forEach((card) => {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = serviceCardHtml(svc, { context: 'services' });
    const next = wrapper.firstElementChild;
    if (next) {
      card.replaceWith(next);
      bindServiceCards(next.parentElement || document);
    }
  });
}

function updateEditMacVisibility() {
  const wrap = $('#edit-mac-wrap');
  if (!wrap) return;
  wrap.classList.toggle('hidden', !$('#edit-wol-enabled')?.checked);
}

const identifySnapshots = { edit: null, add: null };

function setIdentifyUndoVisible(prefix, visible) {
  const undoBtn = $(`#${prefix}-identify-undo`);
  if (!undoBtn) return;
  undoBtn.classList.toggle('hidden', !visible);
}

function clearIdentifyStatus(prefix, { keepUndo = false } = {}) {
  const status = $(`#${prefix}-identify-status`);
  if (!status) return;
  status.classList.add('hidden');
  status.textContent = '';
  status.classList.remove('identify-status--ok', 'identify-status--warn');
  if (!keepUndo) {
    identifySnapshots[prefix] = null;
    setIdentifyUndoVisible(prefix, false);
  }
}

function clearEditIdentifyStatus(opts) {
  clearIdentifyStatus('edit', opts);
}

function captureIdentifySnapshot(prefix) {
  return {
    name: $(`#${prefix}-name`)?.value || '',
    url: $(`#${prefix}-url`)?.value || '',
    category: $(`#${prefix}-category`)?.value || '',
    icon: ($(`#${prefix}-icon`)?.value || 'globe').toLowerCase(),
    icon_url: $(`#${prefix}-icon-url`)?.value || '',
    description: $(`#${prefix}-description`)?.value || '',
    has_login: !!$(`#${prefix}-has-login`)?.checked,
  };
}

function applyIdentifySnapshot(prefix, snapshot) {
  if (!snapshot) return;
  $(`#${prefix}-name`).value = snapshot.name || '';
  $(`#${prefix}-url`).value = snapshot.url || '';
  $(`#${prefix}-category`).value = snapshot.category || '';
  populateServiceIconSelect(snapshot.icon || 'globe', `${prefix}-icon`);
  $(`#${prefix}-icon`).value = (snapshot.icon || 'globe').toLowerCase();
  $(`#${prefix}-icon-url`).value = snapshot.icon_url || '';
  const descEl = $(`#${prefix}-description`);
  if (descEl) descEl.value = snapshot.description || '';
  const loginEl = $(`#${prefix}-has-login`);
  if (loginEl) loginEl.checked = !!snapshot.has_login;
  updateServiceIconPreview(prefix);
}

function formatIdentifyConfidence(confidence) {
  const key = `modal.edit.identifyConfidence.${confidence || 'low'}`;
  const translated = t(key);
  return translated === key ? confidence : translated;
}

function formatIdentifyFields(fields = []) {
  if (!Array.isArray(fields) || fields.length === 0) return '—';
  return fields.map((field) => {
    const key = `modal.edit.identifyField.${field}`;
    const translated = t(key);
    return translated === key ? field : translated;
  }).join(', ');
}

async function identifyServiceModal(prefix) {
  const name = $(`#${prefix}-name`)?.value.trim() || '';
  const url = $(`#${prefix}-url`)?.value.trim() || '';
  if (!name && !url) {
    showToast(t('modal.edit.identifyNeedInput'), 'error');
    return;
  }

  const snapshot = captureIdentifySnapshot(prefix);
  const btn = $(`#${prefix}-identify`);
  const status = $(`#${prefix}-identify-status`);
  const prevLabel = btn?.textContent;
  if (btn) {
    btn.disabled = true;
    btn.textContent = t('modal.edit.identifyRunning');
  }

  try {
    const result = await api('/api/services/identify', {
      method: 'POST',
      body: JSON.stringify({
        name: name || null,
        url: url || null,
        category: $(`#${prefix}-category`)?.value.trim() || null,
        icon: ($(`#${prefix}-icon`)?.value || 'globe').toLowerCase(),
        icon_url: $(`#${prefix}-icon-url`)?.value.trim() || null,
        description: $(`#${prefix}-description`)?.value.trim() || null,
        has_login: $(`#${prefix}-has-login`)?.checked,
      }),
    });

    const s = result.suggestion || {};
    if (s.name) $(`#${prefix}-name`).value = s.name;
    if (s.url) $(`#${prefix}-url`).value = s.url;
    if (s.category) $(`#${prefix}-category`).value = s.category;
    if (s.icon) {
      populateServiceIconSelect(s.icon, `${prefix}-icon`);
      $(`#${prefix}-icon`).value = s.icon.toLowerCase();
    }
    if (s.icon_url !== undefined && s.icon_url !== null) $(`#${prefix}-icon-url`).value = s.icon_url;
    else if (s.icon_url === null && result.matched) $(`#${prefix}-icon-url`).value = '';
    const descEl = $(`#${prefix}-description`);
    if (s.description && descEl) descEl.value = s.description;
    const loginEl = $(`#${prefix}-has-login`);
    if (s.has_login !== undefined && s.has_login !== null && loginEl) {
      loginEl.checked = !!s.has_login;
    }
    updateServiceIconPreview(prefix);
    const changed = Array.isArray(result.changed_fields) && result.changed_fields.length > 0;
    identifySnapshots[prefix] = changed ? snapshot : null;
    setIdentifyUndoVisible(prefix, changed);

    if (status) {
      status.classList.remove('hidden', 'identify-status--ok', 'identify-status--warn');
      if (result.matched) {
        const fields = formatIdentifyFields(result.changed_fields || []);
        const tags = (result.tags || []).join(', ');
        status.textContent = t(tags ? 'modal.edit.identifySuccessWithTags' : 'modal.edit.identifySuccess', {
          confidence: formatIdentifyConfidence(result.confidence),
          fields,
          tags: tags || '—',
        });
        status.classList.add('identify-status--ok');
      } else {
        status.textContent = t('modal.edit.identifyNoMatch');
        status.classList.add('identify-status--warn');
      }
    }
  } catch (err) {
    showToast(err.message || t('modal.edit.identifyError'), 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = prevLabel || t('modal.edit.identify');
    }
  }
}

async function identifyServiceEdit() {
  return identifyServiceModal('edit');
}

function openAddServiceModal() {
  populateServiceCategorySuggestions();
  populateServiceIconSelect('globe', 'add-icon');
  clearIdentifyStatus('add');
  $('#add-name').value = '';
  $('#add-url').value = '';
  $('#add-category').value = t('modal.key.other');
  $('#add-icon').value = 'globe';
  $('#add-icon-url').value = '';
  $('#add-description').value = '';
  $('#add-pinned').checked = false;
  $('#add-has-login').checked = false;
  updateServiceIconPreview('add');
  openModal('add-modal');
}

function resetAddServiceForm() {
  $('#add-name').value = '';
  $('#add-url').value = '';
  $('#add-category').value = t('modal.key.other');
  $('#add-icon-url').value = '';
  $('#add-description').value = '';
  $('#add-pinned').checked = false;
  $('#add-has-login').checked = false;
  clearIdentifyStatus('add');
  updateServiceUrlDuplicateHint('add');
}

async function saveServiceAdd() {
  const name = $('#add-name').value.trim();
  const url = $('#add-url').value.trim();
  const category = $('#add-category').value.trim() || t('modal.key.other');
  const icon = ($('#add-icon').value || 'globe').toLowerCase();
  const iconUrlRaw = $('#add-icon-url').value.trim();
  const description = $('#add-description').value.trim() || null;
  const pinned = $('#add-pinned').checked;
  const has_login = $('#add-has-login').checked;
  if (!name || !url) return showToast(t('alert.serviceFields'), 'error');
  await api('/api/services', {
    method: 'POST',
    body: JSON.stringify({
      name,
      url,
      category,
      icon,
      icon_url: iconUrlRaw || null,
      description,
      pinned,
      has_login,
    }),
  });
  closeModal('add-modal');
  resetAddServiceForm();
  await loadDashboard();
}

function openServiceEditModal(id) {
  const svc = services.find((s) => s.id === id);
  if (!svc) return;
  populateServiceCategorySuggestions();
  populateServiceIconSelect(svc.icon || 'globe');
  clearEditIdentifyStatus();
  $('#edit-id').value = id;
  $('#edit-name').value = svc.name;
  $('#edit-url').value = svc.protocol === 'host' ? '' : (svc.url || '');
  $('#edit-category').value = svc.category || t('modal.key.other');
  $('#edit-icon').value = (svc.icon || 'globe').toLowerCase();
  $('#edit-icon-url').value = svc.icon_url || '';
  $('#edit-description').value = svc.description || '';
  $('#edit-pinned').checked = !!svc.pinned;
  $('#edit-has-login').checked = !!svc.has_login;
  $('#edit-wol-enabled').checked = !!svc.wol_enabled;
  $('#edit-mac').value = svc.mac_address || '';
  updateEditMacVisibility();
  updateEditServiceIconPreview();
  updateServiceUrlDuplicateHint('edit', id);
  openModal('edit-modal');
}

function undoServiceIdentify(prefix) {
  if (!identifySnapshots[prefix]) return;
  applyIdentifySnapshot(prefix, identifySnapshots[prefix]);
  clearIdentifyStatus(prefix);
  const status = $(`#${prefix}-identify-status`);
  if (!status) return;
  status.classList.remove('hidden', 'identify-status--ok', 'identify-status--warn');
  status.textContent = t('modal.edit.identifyUndoDone');
}

function undoServiceIdentifyEdit() {
  undoServiceIdentify('edit');
}

async function saveServiceEdit() {
  const id = Number($('#edit-id').value);
  const name = $('#edit-name').value.trim();
  const url = $('#edit-url').value.trim();
  const category = $('#edit-category').value.trim() || t('modal.key.other');
  const icon = ($('#edit-icon').value || 'globe').toLowerCase();
  const iconUrlRaw = $('#edit-icon-url').value.trim();
  const description = $('#edit-description').value.trim() || null;
  const pinned = $('#edit-pinned').checked;
  const has_login = $('#edit-has-login').checked;
  const wol_enabled = $('#edit-wol-enabled').checked;
  const mac_address = wol_enabled ? ($('#edit-mac').value.trim() || null) : null;
  const svc = services.find((s) => s.id === id);
  const isHostOnly = svc?.protocol === 'host' || svc?.port === 0;
  if (!name) return showToast(t('alert.serviceFields'), 'error');
  if (!isHostOnly && !url) return showToast(t('alert.serviceFields'), 'error');
  if (wol_enabled && !mac_address) return showToast(t('modal.edit.macRequired'), 'error');
  const payload = {
    name, category, icon, icon_url: iconUrlRaw || null, description, pinned, has_login, wol_enabled, mac_address,
  };
  if (!isHostOnly) payload.url = url;
  const updated = await api(`/api/services/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  const idx = services.findIndex((s) => s.id === id);
  if (idx >= 0) services[idx] = normalizeService(updated);
  closeModal('edit-modal');
  refreshServiceViews();
}

function renderServices() {
  normalizeFilterState();
  renderAccessFilters();
  renderAvailabilityFilters();
  if (appSettings.show_category_filters !== false) {
    renderFilters();
  } else {
    $('#category-filters').innerHTML = '';
  }
  renderNetworkFilters();

  const searchMatches = filterBySearch(services);
  const hiddenByFilter = serviceSearch.trim() ? countHiddenByFilters(searchMatches) : 0;
  const filtered = applyServiceFilters(searchMatches);

  const container = $('#services-container');
  const empty = $('#empty-state');
  const gridClass = `services-grid ${gridDensityClass()}`.trim();

  if (filtered.length === 0) {
    container.innerHTML = '';
    renderSearchFilterHint(0);
    updateServicesEmptyState(hiddenByFilter);
    return;
  }

  empty.classList.add('hidden');
  renderSearchFilterHint(hiddenByFilter);

  const grouped = appSettings.services_grouped !== false;
  const showGrouped = grouped && accessFilter === 'all' && availabilityFilter === 'all' && activeFilter === 'all' && networkFilter === 'all';
  const withLogin = filtered.filter((s) => s.has_login === true);
  const withoutLogin = filtered.filter((s) => !s.has_login);

  if (showGrouped && withLogin.length && withoutLogin.length) {
    container.innerHTML = `
      <section class="services-section">
        <h3 class="services-section-title">🔐 ${t('section.withLogin')} <span class="count">${withLogin.length}</span></h3>
        <div class="${gridClass}">${withLogin.map(serviceCardHtml).join('')}</div>
      </section>
      <section class="services-section">
        <h3 class="services-section-title">🌐 ${t('section.public')} <span class="count">${withoutLogin.length}</span></h3>
        <div class="${gridClass}">${withoutLogin.map(serviceCardHtml).join('')}</div>
      </section>`;
  } else {
    container.innerHTML = `<div class="${gridClass}">${filtered.map(serviceCardHtml).join('')}</div>`;
  }

  bindServiceCards(container);
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

let scrollLockY = 0;

function countOpenModals() {
  return $$('.modal').filter((m) => !m.classList.contains('hidden')).length;
}

function closeIconPopover() {
  $$('.icon-picker-popover').forEach((el) => el.remove());
}

function isPageScrollLocked() {
  return document.body.classList.contains('modal-open')
    || document.body.style.position === 'fixed';
}

function setPageScrollLocked(locked) {
  if (locked) {
    if (!isPageScrollLocked()) {
      scrollLockY = window.scrollY;
      document.body.classList.add('modal-open');
      document.body.style.position = 'fixed';
      document.body.style.top = `-${scrollLockY}px`;
      document.body.style.left = '0';
      document.body.style.right = '0';
      document.body.style.width = '100%';
    }
    return;
  }
  document.body.classList.remove('modal-open');
  document.body.style.position = '';
  document.body.style.top = '';
  document.body.style.left = '';
  document.body.style.right = '';
  document.body.style.width = '';
  window.scrollTo(0, scrollLockY);
}

function syncPageScrollLock() {
  setPageScrollLocked(countOpenModals() > 0);
}

function reconcilePageScrollLock() {
  const shouldLock = countOpenModals() > 0;
  const locked = isPageScrollLocked();
  if (shouldLock !== locked) setPageScrollLocked(shouldLock);
}

function guardLayoutWidth(label, fn) {
  const wBefore = document.documentElement.clientWidth;
  fn();
  requestAnimationFrame(() => {
    const wAfter = document.documentElement.clientWidth;
    if (wAfter !== wBefore) {
      console.warn(`[NetDash] Layout width shifted after ${label}: ${wBefore}px → ${wAfter}px`);
    }
  });
}

function openModal(id) {
  const el = $(`#${id}`);
  if (!el || !el.classList.contains('hidden')) return;
  el.classList.remove('hidden');
  syncPageScrollLock();
}

function closeModal(id) {
  const el = $(`#${id}`);
  if (!el || el.classList.contains('hidden')) return;
  el.classList.add('hidden');
  try {
    closeIconPopover();
  } finally {
    syncPageScrollLock();
  }
}

const SCAN_PHASE_KEYS = {
  ping: 'scan.phase.ping',
  ports: 'scan.phase.ports',
  identify: 'scan.phase.identify',
  done: 'scan.phase.done',
};

function formatScanStatus(status) {
  const phase = t(SCAN_PHASE_KEYS[status.progress_phase] || 'scan.phase.default');
  const network = status.cidr || t('scan.localNetwork');
  if (status.found_count > 0) {
    return `${phase} · ${network} · ${t('scan.foundCount', { count: status.found_count })}`;
  }
  if (status.progress_total > 0 && status.progress_phase === 'ping') {
    const pct = Math.round((status.progress_current / status.progress_total) * 100);
    return `${phase} · ${pct}% · ${network}`;
  }
  if (status.progress_total > 0 && status.progress_phase === 'ports') {
    const pct = Math.round((status.progress_current / status.progress_total) * 100);
    return `${phase} · ${pct}% · ${network}`;
  }
  return `${phase} · ${network}`;
}

async function startScan(cidr, fullScan = false) {
  closeModal('scan-modal');
  $('#scan-bar').classList.remove('hidden');
  $('#scan-btn').disabled = true;
  $('#scan-status-text').textContent = t('scan.starting', { network: cidr || t('scan.localNetwork') });

  let job;
  try {
    job = await api('/api/scan', {
      method: 'POST',
      body: JSON.stringify({ cidr: cidr || null, full_scan: fullScan }),
    });
  } catch (err) {
    $('#scan-bar').classList.add('hidden');
    $('#scan-btn').disabled = false;
    showToast(err.message || t('alert.scanStart'), 'error');
    return;
  }

  if (scanPollInterval) clearInterval(scanPollInterval);
  scanPollInterval = setInterval(async () => {
    try {
      const status = await api(`/api/scan/${job.id}`);
      $('#scan-status-text').textContent = formatScanStatus(status);

      if (status.status === 'running' && status.found_count > 0) {
        await loadDashboard();
      }

      if (status.status === 'completed') {
        clearInterval(scanPollInterval);
        $('#scan-bar').classList.add('hidden');
        $('#scan-btn').disabled = false;
        $('#scan-status-text').textContent = '';
        await loadDashboard();
        if (status.found_count === 0) {
          showToast(t('scan.noResults'), 'info');
        }
      } else if (status.status === 'failed') {
        clearInterval(scanPollInterval);
        $('#scan-bar').classList.add('hidden');
        $('#scan-btn').disabled = false;
        showToast(t('scan.failed'), 'error');
      }
    } catch {
      clearInterval(scanPollInterval);
      $('#scan-bar').classList.add('hidden');
      $('#scan-btn').disabled = false;
    }
  }, 1500);
}

// Events
$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('#login-error').classList.add('hidden');
  try {
    await login($('#username').value, $('#password').value);
  } catch (err) {
    showLoginError(err.message || t('error.login'));
  }
});

$('#logout-btn').addEventListener('click', logout);
$('#nav-home-btn')?.addEventListener('click', () => navigateTo('home'));
$('#nav-services-btn')?.addEventListener('click', () => navigateTo('services'));
$('#goto-services-btn')?.addEventListener('click', () => navigateTo('services'));
$('#scan-btn').addEventListener('click', () => openModal('scan-modal'));
$('#add-btn').addEventListener('click', () => openAddServiceModal());
const debouncedRenderServices = debounce(renderServices, 200);

$('#services-search').addEventListener('input', (e) => {
  serviceSearch = e.target.value;
  debouncedRenderServices();
});

$('#empty-clear-search')?.addEventListener('click', () => {
  serviceSearch = '';
  const input = $('#services-search');
  if (input) input.value = '';
  renderServices();
});

function readSettingsFromForm() {
  return {
    title: $('#settings-title').value.trim() || 'NetDash',
    subtitle: $('#settings-subtitle').value.trim(),
    theme: getSelectedTheme(),
    accent_color: $('#settings-accent').value,
    footer_text: $('#settings-footer').value.trim(),
    language: $('#settings-language').value,
    author_name: $('#settings-author-name').value.trim(),
    author_url: $('#settings-author-url').value.trim(),
    author_bio: '',
    about_project: $('#settings-about-project').value,
    scan_cidr_default: $('#settings-scan-cidr').value.trim() || null,
    full_scan_default: $('#settings-full-scan').checked,
    host_scan_ports: $('#settings-host-ports').value.trim() || '22,445,3389,5900',
    host_only_entries: $('#settings-host-only').checked,
    stale_remove_days: parseInt($('#settings-stale-days').value, 10) || 0,
    wol_broadcast_ip: $('#settings-wol-broadcast').value.trim() || '255.255.255.255',
    wol_port: parseInt($('#settings-wol-port').value, 10) || 9,
    sol_port: parseInt($('#settings-sol-port').value, 10) || 9,
    gptwol_url: $('#settings-gptwol-url').value.trim() || null,
    health_check_enabled: $('#settings-health-enabled').checked,
    health_check_interval: parseInt($('#settings-health-interval').value, 10) || 60,
    show_clock: $('#settings-show-clock').checked,
    show_vault: $('#settings-show-vault').checked,
    show_notes: $('#settings-show-notes').checked,
    show_stats: $('#settings-show-stats').checked,
    show_category_filters: $('#settings-show-category-filters').checked,
    show_service_urls: $('#settings-show-service-urls').checked,
    show_ports: $('#settings-show-ports').checked,
    services_grouped: $('#settings-services-grouped').value === 'true',
    default_access_filter: $('#settings-default-access').value,
    services_columns: $('#settings-services-columns').value,
    card_style: $('#settings-card-style').value,
    pinned_card_size: $('#settings-pinned-card-size').value,
    custom_css: $('#settings-custom-css').value,
    favicon_url: $('#settings-favicon').value.trim() || null,
    show_about: false,
  };
}

function fillSettingsForm() {
  $('#settings-title').value = appSettings.title || '';
  $('#settings-subtitle').value = appSettings.subtitle || '';
  updateThemePickerSelection(appSettings.theme || DEFAULT_THEME);
  $('#settings-accent').value = appSettings.accent_color || '#22c55e';
  updateAccentHex();
  $('#settings-footer').value = appSettings.footer_text || '';
  $('#settings-favicon').value = appSettings.favicon_url || '';
  $('#settings-custom-css').value = appSettings.custom_css || '';
  $('#settings-language').value = appSettings.language || 'pl';
  $('#settings-author-name').value = appSettings.author_name || '';
  $('#settings-author-url').value = appSettings.author_url || '';
  $('#settings-about-project').value = appSettings.about_project || '';
  $('#settings-scan-cidr').value = appSettings.scan_cidr_default || '';
  updateDockerScanWarning(window.__netdashNetwork || null, appSettings);
  $('#settings-full-scan').checked = !!appSettings.full_scan_default;
  $('#settings-host-ports').value = appSettings.host_scan_ports || '22,445,3389,5900';
  $('#settings-host-only').checked = appSettings.host_only_entries !== false;
  $('#settings-stale-days').value = appSettings.stale_remove_days ?? 0;
  $('#settings-wol-broadcast').value = appSettings.wol_broadcast_ip || '255.255.255.255';
  $('#settings-wol-port').value = appSettings.wol_port ?? 9;
  $('#settings-sol-port').value = appSettings.sol_port ?? appSettings.wol_port ?? 9;
  $('#settings-gptwol-url').value = appSettings.gptwol_url || '';
  $('#settings-health-enabled').checked = appSettings.health_check_enabled !== false;
  $('#settings-health-interval').value = appSettings.health_check_interval ?? 60;
  renderPowerDevicesList();
  $('#settings-show-clock').checked = appSettings.show_clock !== false;
  $('#settings-show-vault').checked = appSettings.show_vault !== false;
  $('#settings-show-notes').checked = appSettings.show_notes !== false;
  $('#settings-show-stats').checked = appSettings.show_stats !== false;
  $('#settings-show-category-filters').checked = appSettings.show_category_filters !== false;
  $('#settings-show-service-urls').checked = appSettings.show_service_urls !== false;
  $('#settings-show-ports').checked = appSettings.show_ports !== false;
  $('#settings-services-grouped').value = appSettings.services_grouped === false ? 'false' : 'true';
  $('#settings-default-access').value = appSettings.default_access_filter || 'all';
  $('#settings-services-columns').value = appSettings.services_columns || 'normal';
  $('#settings-card-style').value = appSettings.card_style || 'detailed';
  $('#settings-pinned-card-size').value = dashboardLayout();
  solScriptContext = { mac: null, port: null };
  refreshSolScriptPreviews();
  refreshSettingsFaviconStatus();
  syncSettingsFaviconDetails();
}

function previewSettingsFromForm() {
  appSettings = { ...appSettings, ...readSettingsFromForm() };
  applyDataTheme(appSettings.theme || DEFAULT_THEME);
  setAccentColor(appSettings.accent_color || '#22c55e');
  updateAccentHex();
  $('#app-title').textContent = appSettings.title || 'NetDash';
  $('#app-subtitle').textContent = appSettings.subtitle || t('app.tagline');
  applyCustomCss(appSettings.custom_css || '');
  applyFavicon(appSettings.favicon_url);
  applyCustomLogo();
  applyLayout();
  applyDefaultAccessFilter(appSettings.default_access_filter);
  refreshServiceViews();
}

let settingsSnapshot = null;

function clearPasswordForm() {
  $('#settings-password-current').value = '';
  $('#settings-password-new').value = '';
  $('#settings-password-confirm').value = '';
  showPasswordMessage('');
}

function showPasswordMessage(message, type = '') {
  const el = $('#settings-password-message');
  if (!el) return;
  el.textContent = message;
  el.classList.remove('hidden', 'success', 'error');
  if (!message) {
    el.classList.add('hidden');
    return;
  }
  if (type) el.classList.add(type);
}

function showBackupMessage(message, type = '') {
  const el = $('#settings-backup-message');
  if (!el) return;
  el.textContent = message;
  el.classList.remove('hidden', 'success', 'error');
  if (!message) {
    el.classList.add('hidden');
    return;
  }
  if (type) el.classList.add(type);
}

function backupFilename() {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
  return `netdash-backup-${stamp}.json`;
}

async function exportSettingsBackup() {
  showBackupMessage('');
  const btn = $('#settings-backup-export');
  if (btn) btn.disabled = true;
  try {
    const data = await api('/api/settings/export');
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = backupFilename();
    link.click();
    URL.revokeObjectURL(url);
    showBackupMessage(t('settings.backup.exportSuccess'), 'success');
  } catch (err) {
    showBackupMessage(err.message || t('settings.backup.error.generic'), 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function importSettingsBackup(file) {
  if (!file) return;
  showBackupMessage('');
  let payload;
  try {
    payload = JSON.parse(await file.text());
  } catch {
    showBackupMessage(t('settings.backup.error.invalidJson'), 'error');
    return;
  }
  if (payload.format !== 'netdash-backup') {
    showBackupMessage(t('settings.backup.error.invalidFormat'), 'error');
    return;
  }
  if (!confirm(t('settings.backup.importConfirm'))) return;

  const btn = $('#settings-backup-import');
  if (btn) btn.disabled = true;
  try {
    appSettings = await api('/api/settings/import', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    applyDefaultAccessFilter(appSettings.default_access_filter);
    activeFilter = 'all';
    networkFilter = 'all';
    await setLanguage(appSettings.language || 'pl');
    applyTheme();
    await loadDashboard();
    showBackupMessage(t('settings.backup.importSuccess'), 'success');
  } catch (err) {
    showBackupMessage(err.message || t('settings.backup.error.generic'), 'error');
  } finally {
    if (btn) btn.disabled = false;
    const input = $('#settings-backup-file');
    if (input) input.value = '';
  }
}

async function importHomerConfig(file) {
  if (!file) return;
  showBackupMessage('');
  const btn = $('#settings-homer-import');
  if (btn) btn.disabled = true;
  try {
    const form = new FormData();
    form.append('file', file);
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${API}/api/services/import/homer`, {
      method: 'POST',
      headers,
      body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(translateApiDetail(data.detail) || `HTTP ${res.status}`);
    }
    await loadServices();
    updateStats();
    showBackupMessage(
      t('settings.homer.importSuccess', { imported: data.imported, skipped: data.skipped || 0 }),
      'success',
    );
  } catch (err) {
    showBackupMessage(err.message || t('settings.homer.importError'), 'error');
  } finally {
    if (btn) btn.disabled = false;
    const input = $('#settings-homer-file');
    if (input) input.value = '';
  }
}

async function changePassword(currentPassword, newPassword) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}/api/auth/password`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (res.status === 401) {
    throw new Error(t('settings.password.error.wrong'));
  }
  if (res.status === 422) {
    throw new Error(t('settings.password.error.short'));
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(translateApiDetail(err.detail) || `HTTP ${res.status}`);
  }
}

$('#settings-btn').addEventListener('click', () => {
  fillSettingsForm();
  clearPasswordForm();
  showBackupMessage('');
  settingsSnapshot = { ...appSettings };
  renderPowerDevicesList();
  renderAboutPanel();
  const activeTab = $('.settings-tab.active')?.dataset.tab || 'general';
  updateSettingsFooter(activeTab);
  openModal('settings-modal');
});

$('#settings-backup-export')?.addEventListener('click', exportSettingsBackup);
$('#settings-backup-import')?.addEventListener('click', () => $('#settings-backup-file')?.click());
$('#settings-backup-file')?.addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (file) importSettingsBackup(file);
});
$('#settings-homer-import')?.addEventListener('click', () => $('#settings-homer-file')?.click());
$('#settings-homer-file')?.addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (file) importHomerConfig(file);
});

const SETTINGS_READONLY_TABS = new Set(['about', 'backup', 'account']);

function updateSettingsFooter(tabId) {
  const footer = $('#settings-modal-footer');
  if (!footer) return;
  footer.classList.toggle('settings-footer--hidden', SETTINGS_READONLY_TABS.has(tabId));
}

function switchSettingsTab(tabId) {
  $$('.settings-tab').forEach((t) => {
    t.classList.remove('active');
    t.setAttribute('aria-selected', 'false');
  });
  $$('.settings-panel').forEach((p) => p.classList.remove('active'));
  const tab = $(`.settings-tab[data-tab="${tabId}"]`);
  tab?.classList.add('active');
  tab?.setAttribute('aria-selected', 'true');
  const panel = $(`.settings-panel[data-panel="${tabId}"]`);
  panel?.classList.add('active');
  if (panel) panel.scrollTop = 0;
  updateSettingsFooter(tabId);
  if (tabId === 'about') renderAboutPanel();
  if (tabId === 'power') {
    solScriptContext = { mac: null, port: null };
    refreshSolScriptPreviews();
  }
}

$$('.settings-tab').forEach((tab) => {
  tab.addEventListener('click', () => switchSettingsTab(tab.dataset.tab));
});

let solScriptOs = 'linux';
let solScriptContext = { mac: null, port: null };

function normalizeSolMac(mac) {
  if (!mac) return null;
  const cleaned = String(mac).trim().replace(/-/g, ':').toUpperCase();
  return /^([0-9A-F]{2}:){5}[0-9A-F]{2}$/.test(cleaned) ? cleaned : null;
}

function getSolScriptPort(overridePort) {
  if (overridePort != null && !Number.isNaN(overridePort)) return overridePort;
  if (solScriptContext.port != null) return solScriptContext.port;
  const fromForm = parseInt($('#settings-sol-port')?.value, 10);
  if (fromForm > 0) return fromForm;
  return appSettings.sol_port ?? appSettings.wol_port ?? 9;
}

function getSolScriptMac(overrideMac) {
  const raw = overrideMac ?? solScriptContext.mac;
  return normalizeSolMac(raw);
}

function pythonSolListenerBody(port, mac) {
  const macComment = mac
    ? `Target MAC ${mac} (packet uses reversed byte order)`
    : 'Auto-detect: match any local interface MAC';
  return `#!/usr/bin/env python3
"""NetDash Sleep-on-LAN UDP listener — ${macComment}"""
import glob
import socket
import subprocess
import sys

PORT = ${port}
TARGET_MAC = ${mac ? `"${mac}"` : '""'}

def normalize(mac):
    return mac.replace("-", ":").upper()

def local_macs():
    macs = []
    for path in glob.glob("/sys/class/net/*/address"):
        iface = path.split("/")[4]
        if iface == "lo":
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                value = fh.read().strip()
            if value and value != "00:00:00:00:00:00":
                macs.append(normalize(value))
        except OSError:
            pass
    return macs

def extract_mac(data):
    if len(data) < 102 or data[:6] != b"\\xff" * 6:
        return None
    chunk = data[6:12]
    return ":".join(f"{b:02x}" for b in chunk)

def packet_matches(packet_mac):
    rev = bytes(int(p, 16) for p in packet_mac.split(":"))[::-1]
    normal = ":".join(f"{b:02x}" for b in rev).upper()
    if TARGET_MAC:
        return normal == normalize(TARGET_MAC)
    return normal in local_macs()

def suspend():
    if sys.platform.startswith("linux"):
        for cmd in (["systemctl", "suspend"], ["pm-suspend"]):
            try:
                subprocess.run(cmd, check=True)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        raise SystemExit("suspend failed — install systemd or pm-utils")
    if sys.platform == "darwin":
        subprocess.run(["pmset", "sleepnow"], check=True)
        return
    raise SystemExit("unsupported platform")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", PORT))
    print(f"NetDash SOL listening on UDP {PORT}", flush=True)
    while True:
        data, addr = sock.recvfrom(1024)
        mac = extract_mac(data)
        if mac and packet_matches(mac):
            print(f"SOL trigger from {addr[0]} packet_mac={mac}", flush=True)
            suspend()

if __name__ == "__main__":
    main()
`;
}

function generateLinuxSolScript(port, mac) {
  const macArg = mac || '';
  const macComment = mac
    ? `# MAC: ${mac} (NetDash sends reversed bytes in magic packet)`
    : '# MAC: auto-detect primary interface (or pass as 1st argument)';
  return `#!/bin/bash
# NetDash Sleep-on-LAN installer (Linux)
# UDP port: ${port}
${macComment}
# Usage: sudo bash install-netdash-sol.sh [AA:BB:CC:DD:EE:FF]
# Requires: python3, systemd. Allow UDP ${port} from NetDash server subnet.

set -euo pipefail
SOL_PORT=${port}
MAC_ARG="\$1"
[[ -z "\$MAC_ARG" ]] && MAC_ARG="${macArg}"
INSTALL_DIR="/opt/netdash-sol"
SERVICE_NAME="netdash-sol"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0 [MAC]" >&2
  exit 1
fi

command -v python3 >/dev/null 2>&1 || {
  echo "Installing python3..."
  if command -v apt-get >/dev/null; then apt-get update && apt-get install -y python3
  elif command -v dnf >/dev/null; then dnf install -y python3
  elif command -v pacman >/dev/null; then pacman -Sy --noconfirm python
  else echo "Install python3 manually" >&2; exit 1; fi
}

mkdir -p "$INSTALL_DIR"
cat > "$INSTALL_DIR/listener.py" << 'PYEOF'
${pythonSolListenerBody(port, mac || null)}
PYEOF
chmod 755 "$INSTALL_DIR/listener.py"

if [[ -n "$MAC_ARG" ]]; then
  sed -i "s/^TARGET_MAC = .*/TARGET_MAC = \\"$MAC_ARG\\"/" "$INSTALL_DIR/listener.py"
fi

cat > "/etc/systemd/system/\${SERVICE_NAME}.service" << EOF
[Unit]
Description=NetDash Sleep-on-LAN listener
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 $INSTALL_DIR/listener.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "\${SERVICE_NAME}.service"

if command -v ufw >/dev/null 2>&1 && ufw status | grep -qi active; then
  ufw allow "${port}/udp" comment "NetDash SOL" || true
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --permanent --add-port=${port}/udp || true
  firewall-cmd --reload || true
else
  iptables -C INPUT -p udp --dport ${port} -j ACCEPT 2>/dev/null || \\
    iptables -I INPUT -p udp --dport ${port} -j ACCEPT
fi

echo "NetDash SOL installed — listening on UDP ${port}"
systemctl status "\${SERVICE_NAME}.service" --no-pager || true
`;
}

function windowsSolListenerBody(port, mac) {
  const macPs = mac ? `"${mac}"` : '$null';
  return `function Normalize-Mac([string]$Mac) {
  if (-not $Mac) { return $null }
  return ($Mac -replace '-', ':').ToUpper()
}

$SolPort = ${port}
$TargetMac = ${macPs}

function Get-LocalMacs {
  Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
    Where-Object Status -eq 'Up' |
    ForEach-Object { Normalize-Mac $_.MacAddress } |
    Where-Object { $_ }
}

function Get-PacketMac([byte[]]$Data) {
  if ($Data.Length -lt 102) { return $null }
  $sync = $Data[0..5]
  if (($sync | Where-Object { $_ -ne 255 }).Count -gt 0) { return $null }
  $chunk = $Data[6..11]
  return (($chunk | ForEach-Object { '{0:X2}' -f $_ }) -join ':')
}

function Test-SolPacket([string]$PacketMac) {
  $bytes = $PacketMac.Split(':') | ForEach-Object { [Convert]::ToByte($_, 16) }
  [array]::Reverse($bytes)
  $normal = (($bytes | ForEach-Object { '{0:X2}' -f $_ }) -join ':').ToUpper()
  if ($TargetMac) { return $normal -eq (Normalize-Mac $TargetMac) }
  return (Get-LocalMacs) -contains $normal
}

function Enter-Suspend {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class PowerProfile {
  [DllImport("powrprof.dll", SetLastError=true)]
  public static extern bool SetSuspendState(bool hibernate, bool forceCritical, bool disableWakeEvent);
}
"@
  [PowerProfile]::SetSuspendState($false, $true, $true) | Out-Null
}

$udp = New-Object System.Net.Sockets.UdpClient $SolPort
Write-Host "NetDash SOL listening on UDP $SolPort"
while ($true) {
  $remote = New-Object System.Net.IPEndPoint ([System.Net.IPAddress]::Any, 0)
  $data = $udp.Receive([ref]$remote)
  $packetMac = Get-PacketMac $data
  if ($packetMac -and (Test-SolPacket $packetMac)) {
    Write-Host "SOL trigger from $($remote.Address) packet_mac=$packetMac"
    Enter-Suspend
  }
}
`;
}

function generateWindowsSolScript(port, mac) {
  const macNote = mac
    ? `# MAC: ${mac}`
    : '# MAC: auto-detect from active adapters';
  return `# NetDash Sleep-on-LAN installer (Windows)
# UDP port: ${port}
${macNote}
# Usage: run PowerShell as Administrator:
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\\install-netdash-sol.ps1
# Registers a logon scheduled task and opens Windows Firewall for UDP ${port}.

#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"
$InstallDir = "$env:ProgramData\\NetDash\\sol"
$TaskName = "NetDash-SOL"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

@'
${windowsSolListenerBody(port, mac)}
'@ | Set-Content -Path "$InstallDir\\listener.ps1" -Encoding UTF8

$fwRule = Get-NetFirewallRule -DisplayName "NetDash SOL" -ErrorAction SilentlyContinue
if (-not $fwRule) {
  New-NetFirewallRule -DisplayName "NetDash SOL" -Direction Inbound -Protocol UDP -LocalPort $SolPort -Action Allow | Out-Null
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \`"$InstallDir\\listener.ps1\`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "NetDash SOL installed — UDP $SolPort, task $TaskName"
`;
}

function generateMacosSolScript(port, mac) {
  const macArg = mac || '';
  const macComment = mac
    ? `# MAC: ${mac}`
    : '# MAC: auto-detect (or pass as 1st argument)';
  return `#!/bin/bash
# NetDash Sleep-on-LAN installer (macOS)
# UDP port: ${port}
${macComment}
# Usage: sudo bash install-netdash-sol.sh [AA:BB:CC:DD:EE:FF]
# Requires: python3. Allow UDP ${port} in System Settings → Network → Firewall.

set -euo pipefail
SOL_PORT=${port}
MAC_ARG="\$1"
[[ -z "\$MAC_ARG" ]] && MAC_ARG="${macArg}"
INSTALL_DIR="/usr/local/libexec/netdash-sol"
PLIST="/Library/LaunchDaemons/com.netdash.sol.plist"
LABEL="com.netdash.sol"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0 [MAC]" >&2
  exit 1
fi

command -v python3 >/dev/null 2>&1 || { echo "Install python3 (Xcode CLI or Homebrew)" >&2; exit 1; }

mkdir -p "$INSTALL_DIR"
cat > "$INSTALL_DIR/listener.py" << 'PYEOF'
${pythonSolListenerBody(port, mac || null)}
PYEOF
chmod 755 "$INSTALL_DIR/listener.py"

if [[ -n "$MAC_ARG" ]]; then
  sed -i '' "s/^TARGET_MAC = .*/TARGET_MAC = \\"$MAC_ARG\\"/" "$INSTALL_DIR/listener.py"
fi

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>$INSTALL_DIR/listener.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
EOF

launchctl bootout system "$LABEL" 2>/dev/null || true
launchctl bootstrap system "$PLIST"
launchctl enable "system/$LABEL"
launchctl kickstart -k "system/$LABEL"

echo "NetDash SOL installed — UDP ${port}"
echo "If firewall is enabled, allow python3 incoming UDP ${port}."
`;
}

function generateSolInstallScript(os, opts = {}) {
  const port = getSolScriptPort(opts.port);
  const mac = getSolScriptMac(opts.mac);
  if (os === 'windows') return generateWindowsSolScript(port, mac);
  if (os === 'macos') return generateMacosSolScript(port, mac);
  return generateLinuxSolScript(port, mac);
}

function solScriptFilename(os, mac) {
  const base = mac ? `netdash-sol-${mac.replace(/:/g, '-')}` : 'netdash-sol-install';
  if (os === 'windows') return `${base}.ps1`;
  return `${base}.sh`;
}

function getSolScriptPreviewEl(scope) {
  return scope === 'modal' ? $('#sol-script-modal-preview') : $('#settings-sol-script-preview');
}

function setSolScriptOs(os, scope) {
  solScriptOs = os;
  const root = scope === 'modal' ? '#sol-script-modal' : '#sol-scripts-section';
  $$(`${root} .sol-script-os-tab`).forEach((tab) => {
    const active = tab.dataset.os === os;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  const preview = getSolScriptPreviewEl(scope);
  if (preview) preview.value = generateSolInstallScript(os);
}

function refreshSolScriptPreviews() {
  const script = generateSolInstallScript(solScriptOs);
  const settingsPreview = $('#settings-sol-script-preview');
  const modalPreview = $('#sol-script-modal-preview');
  if (settingsPreview) settingsPreview.value = script;
  if (modalPreview) modalPreview.value = script;
}

async function copySolScript(scope) {
  const preview = getSolScriptPreviewEl(scope);
  if (!preview?.value) return;
  try {
    await navigator.clipboard.writeText(preview.value);
    showToast(t('toast.copied'), 'success');
  } catch {
    preview.select();
    document.execCommand('copy');
    showToast(t('toast.copied'), 'success');
  }
}

function downloadSolScript(scope) {
  const preview = getSolScriptPreviewEl(scope);
  if (!preview?.value) return;
  const mac = getSolScriptMac();
  const blob = new Blob([preview.value], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = solScriptFilename(solScriptOs, mac);
  a.click();
  URL.revokeObjectURL(url);
}

function openSolScriptModal(opts = {}) {
  solScriptContext = {
    mac: normalizeSolMac(opts.mac) || null,
    port: opts.port != null ? parseInt(opts.port, 10) || null : null,
  };
  solScriptOs = 'linux';
  const hint = $('#sol-script-modal-hint');
  if (hint) {
    hint.textContent = solScriptContext.mac
      ? `${t('settings.sol.scripts.serviceHint')} MAC: ${solScriptContext.mac}`
      : t('settings.sol.scripts.hint');
  }
  setSolScriptOs('linux', 'modal');
  openModal('sol-script-modal');
}

function openSolSetupHelp() {
  fillSettingsForm();
  renderPowerDevicesList();
  switchSettingsTab('power');
  openModal('settings-modal');
  requestAnimationFrame(() => {
    const details = $('#sol-setup-help');
    if (details) {
      details.open = true;
      details.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    solScriptContext = { mac: null, port: null };
    refreshSolScriptPreviews();
  });
}

const SETTINGS_PREVIEW_IDS = [
  'settings-title', 'settings-subtitle', 'settings-footer', 'settings-favicon',
  'settings-custom-css', 'settings-accent', 'settings-show-clock', 'settings-show-vault',
  'settings-show-notes', 'settings-show-stats', 'settings-show-category-filters',
  'settings-show-service-urls', 'settings-show-ports', 'settings-services-grouped',
  'settings-default-access', 'settings-services-columns', 'settings-card-style',
  'settings-pinned-card-size',
  'settings-about-project', 'settings-author-name', 'settings-author-url',
];

SETTINGS_PREVIEW_IDS.forEach((id) => {
  const el = $('#' + id);
  if (!el) return;
  const evt = el.tagName === 'SELECT' || el.type === 'checkbox' ? 'change' : 'input';
  el.addEventListener(evt, () => {
    if ($('#settings-modal').classList.contains('hidden')) return;
    previewSettingsFromForm();
    if (id === 'settings-about-project' || id === 'settings-author-name' || id === 'settings-author-url') {
      renderAboutPanel();
    }
  });
});

$('#settings-accent')?.addEventListener('input', updateAccentHex);

$('#settings-theme-picker')?.addEventListener('click', (e) => {
  const card = e.target.closest('.theme-card');
  if (!card) return;
  updateThemePickerSelection(card.dataset.theme);
  if ($('#settings-modal').classList.contains('hidden')) return;
  previewSettingsFromForm();
});

$('#settings-cancel').addEventListener('click', () => {
  if (settingsSnapshot) {
    appSettings = settingsSnapshot;
    applyDefaultAccessFilter(appSettings.default_access_filter);
  }
  applyTheme();
  refreshServiceViews();
  closeModal('settings-modal');
  settingsSnapshot = null;
});

$('#settings-password-change').addEventListener('click', async () => {
  const current = $('#settings-password-current').value;
  const newPwd = $('#settings-password-new').value;
  const confirm = $('#settings-password-confirm').value;
  showPasswordMessage('');

  if (!current) {
    showPasswordMessage(t('settings.password.error.currentRequired'), 'error');
    return;
  }
  if (!newPwd) {
    showPasswordMessage(t('settings.password.error.newRequired'), 'error');
    return;
  }
  if (newPwd.length < 4) {
    showPasswordMessage(t('settings.password.error.short'), 'error');
    return;
  }
  if (newPwd !== confirm) {
    showPasswordMessage(t('settings.password.error.mismatch'), 'error');
    return;
  }

  const btn = $('#settings-password-change');
  btn.disabled = true;
  try {
    await changePassword(current, newPwd);
    clearPasswordForm();
    showPasswordMessage(t('settings.password.success'), 'success');
  } catch (err) {
    showPasswordMessage(err.message || t('settings.password.error.generic'), 'error');
  } finally {
    btn.disabled = false;
  }
});

$('#settings-save').addEventListener('click', async () => {
  const payload = readSettingsFromForm();
  const newLang = payload.language;
  appSettings = await api('/api/settings', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  if (newLang !== currentLang) await setLanguage(newLang);
  applyDefaultAccessFilter(appSettings.default_access_filter);
  applyTheme();
  refreshServiceViews();
  startHealthPolling();
  closeModal('settings-modal');
  settingsSnapshot = null;
});

$('#add-key-btn').addEventListener('click', () => openKeyModal());
$('#add-note-btn').addEventListener('click', () => openNoteModal());
$('#keys-search').addEventListener('input', renderKeys);
$('#notes-search').addEventListener('input', renderNotes);

$('#key-cancel').addEventListener('click', () => closeModal('key-modal'));
$('#key-save').addEventListener('click', saveKey);
$('#note-cancel').addEventListener('click', () => closeModal('note-modal'));
$('#note-save').addEventListener('click', saveNote);
$('#note-delete').addEventListener('click', async () => {
  const editId = $('#note-edit-id').value;
  if (!editId || !confirm(t('confirm.delete.note'))) return;
  await api(`/api/notes/${editId}`, { method: 'DELETE' });
  closeModal('note-modal');
  await loadDashboard();
});

$$('.modal-backdrop').forEach((b) => {
  b.addEventListener('click', () => {
    const modal = b.closest('.modal');
    if (modal?.id) closeModal(modal.id);
  });
});

$('#scan-cancel').addEventListener('click', () => closeModal('scan-modal'));
$('#scan-start').addEventListener('click', () => {
  const cidr = $('#cidr-input').value.trim();
  const fullScan = $('#full-scan').checked;
  startScan(cidr || null, fullScan);
});

$('#add-cancel').addEventListener('click', () => closeModal('add-modal'));
$('#edit-cancel').addEventListener('click', () => closeModal('edit-modal'));
$('#edit-identify')?.addEventListener('click', () => identifyServiceEdit());
$('#edit-identify-undo')?.addEventListener('click', () => undoServiceIdentifyEdit());
$('#add-identify')?.addEventListener('click', () => identifyServiceModal('add'));
$('#add-identify-undo')?.addEventListener('click', () => undoServiceIdentify('add'));
$('#edit-icon')?.addEventListener('change', updateEditServiceIconPreview);
$('#edit-icon-url')?.addEventListener('input', updateEditServiceIconPreview);
$('#add-icon')?.addEventListener('change', () => updateServiceIconPreview('add'));
$('#add-icon-url')?.addEventListener('input', () => updateServiceIconPreview('add'));
$('#edit-open-notes')?.addEventListener('click', () => {
  const id = $('#edit-id').value;
  if (!id) return;
  closeModal('edit-modal');
  openServiceNotesModal(Number(id));
});
$('#edit-wol-enabled')?.addEventListener('change', updateEditMacVisibility);
$('#edit-url')?.addEventListener('input', () => {
  const id = Number($('#edit-id')?.value);
  updateServiceUrlDuplicateHint('edit', Number.isFinite(id) && id > 0 ? id : null);
});
$('#add-url')?.addEventListener('input', () => updateServiceUrlDuplicateHint('add'));
$('#edit-save').addEventListener('click', async () => {
  try {
    await saveServiceEdit();
  } catch (err) {
    showToast(err.message || t('error.api.services'), 'error');
  }
});
$('#add-save').addEventListener('click', async () => {
  try {
    await saveServiceAdd();
  } catch (err) {
    showToast(err.message || t('error.api.services'), 'error');
  }
});

$('#service-notes-cancel').addEventListener('click', () => closeModal('service-notes-modal'));
$('#service-notes-sol-help')?.addEventListener('click', () => {
  closeModal('service-notes-modal');
  openSolSetupHelp();
});
$('#service-notes-sol-script')?.addEventListener('click', () => {
  const mac = normalizeSolMac($('#service-notes-mac')?.value);
  const defaultSol = appSettings.sol_port ?? appSettings.wol_port ?? 9;
  const solPortRaw = $('#service-notes-sol-port')?.value.trim();
  const port = solPortRaw ? parseInt(solPortRaw, 10) : defaultSol;
  openSolScriptModal({ mac, port });
});
$('#settings-sol-port')?.addEventListener('input', () => {
  if ($('#settings-modal').classList.contains('hidden')) return;
  solScriptContext = { mac: null, port: null };
  refreshSolScriptPreviews();
});
$$('.sol-script-os-tab').forEach((tab) => {
  tab.addEventListener('click', () => setSolScriptOs(tab.dataset.os, tab.dataset.scope || 'settings'));
});
$('#settings-sol-script-copy')?.addEventListener('click', () => copySolScript('settings'));
$('#settings-sol-script-download')?.addEventListener('click', () => downloadSolScript('settings'));
$('#sol-script-modal-copy')?.addEventListener('click', () => copySolScript('modal'));
$('#sol-script-modal-download')?.addEventListener('click', () => downloadSolScript('modal'));
$('#sol-script-modal-close')?.addEventListener('click', () => closeModal('sol-script-modal'));
$('#service-notes-detect-mac')?.addEventListener('click', async () => {
  const id = $('#service-notes-id').value;
  if (!id) return;
  await lookupServiceMac(id, { auto: false });
});
$('#service-notes-mac')?.addEventListener('input', () => {
  serviceNotesMacAuto = false;
  updateServiceNotesMacHint('manual');
});
$('#service-notes-save').addEventListener('click', async () => {
  const id = $('#service-notes-id').value;
  if (!id) return;
  const svc = services.find((s) => String(s.id) === id);
  const defaultWol = appSettings.wol_port ?? 9;
  const defaultSol = appSettings.sol_port ?? appSettings.wol_port ?? 9;
  const wolPortRaw = $('#service-notes-wol-port').value.trim();
  const solPortRaw = $('#service-notes-sol-port').value.trim();
  const broadcastRaw = $('#service-notes-broadcast').value.trim();
  const wolPort = wolPortRaw ? parseInt(wolPortRaw, 10) : null;
  const solPort = solPortRaw ? parseInt(solPortRaw, 10) : null;
  await api(`/api/services/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({
      service_notes: $('#service-notes-text').value,
      mac_address: $('#service-notes-mac').value.trim() || null,
      wol_enabled: $('#service-notes-wol').checked,
      wol_port: wolPort != null && svc?.wol_port == null && wolPort === defaultWol ? null : wolPort,
      sol_port: solPort != null && svc?.sol_port == null && solPort === defaultSol ? null : solPort,
      broadcast_ip: broadcastRaw || null,
    }),
  });
  closeModal('service-notes-modal');
  await loadDashboard();
});

function renderArpScanResults(devices) {
  const box = $('#arp-scan-results');
  if (!box) return;
  if (!devices.length) {
    box.innerHTML = `<p class="hint">${t('settings.arpScan.empty')}</p>`;
    box.classList.remove('hidden');
    return;
  }
  box.innerHTML = `
    <table class="arp-scan-table">
      <thead><tr>
        <th>${t('settings.arpScan.ip')}</th>
        <th>${t('settings.arpScan.mac')}</th>
        <th>${t('settings.arpScan.hostname')}</th>
        <th></th>
      </tr></thead>
      <tbody>
        ${devices.map((d) => `
          <tr>
            <td><code>${esc(d.ip)}</code></td>
            <td><code>${esc(d.mac)}</code></td>
            <td>${esc(d.hostname || '—')}</td>
            <td><button type="button" class="btn btn-ghost btn-sm arp-assign-btn" data-mac="${esc(d.mac)}" data-ip="${esc(d.ip)}">${t('settings.arpScan.assign')}</button></td>
          </tr>`).join('')}
      </tbody>
    </table>`;
  box.classList.remove('hidden');
  box.querySelectorAll('.arp-assign-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const mac = btn.dataset.mac;
      const ip = btn.dataset.ip;
      const match = services.find((s) => s.host === ip);
      if (match) {
        $('#power-link-service').value = String(match.id);
      }
      $('#power-link-mac').value = mac;
      $('#power-link-enabled').checked = true;
      $('#power-link-mac').focus();
    });
  });
}

$('#arp-scan-btn')?.addEventListener('click', async () => {
  const btn = $('#arp-scan-btn');
  const status = $('#arp-scan-status');
  if (!btn) return;
  btn.disabled = true;
  if (status) status.textContent = t('settings.arpScan.running');
  try {
    const cidr = $('#settings-scan-cidr')?.value.trim() || null;
    const devices = await api('/api/network/arp-scan', {
      method: 'POST',
      body: JSON.stringify(cidr ? { cidr } : {}),
    });
    renderArpScanResults(devices);
    await loadServices();
    if (status) status.textContent = t('settings.arpScan.done', { count: devices.length });
  } catch (err) {
    if (status) status.textContent = err.message || t('settings.arpScan.failed');
    $('#arp-scan-results')?.classList.add('hidden');
  } finally {
    btn.disabled = false;
  }
});

$('#power-link-save').addEventListener('click', async () => {
  const id = $('#power-link-service').value;
  const mac = $('#power-link-mac').value.trim();
  if (!id || !mac) return showToast(t('alert.macRequired'), 'error');
  await api(`/api/services/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({
      mac_address: mac,
      wol_enabled: $('#power-link-enabled').checked,
    }),
  });
  $('#power-link-mac').value = '';
  await loadDashboard();
  fillSettingsForm();
});

initServiceIconPickers();
setupSettingsFaviconUpload();

document.addEventListener('visibilitychange', reconcilePageScrollLock);
window.addEventListener('pageshow', reconcilePageScrollLock);

// Init
(async () => {
  await loadLanguage(localStorage.getItem('netdash_lang') || 'pl');
  applyI18n();
  ['edit', 'add'].forEach((prefix) => {
    refreshIconPickerTabs(prefix);
    refreshIconPickerGrid(prefix);
  });
  await checkServerHealth();
  reconcilePageScrollLock();
  if (token) {
    showView('dashboard-view');
    loadDashboard().catch(handleDashboardLoadError);
  } else {
    showView('login-view');
  }
})();
