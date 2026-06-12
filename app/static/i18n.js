const SUPPORTED_LANGS = ['pl', 'en', 'de', 'uk'];
const I18N_CACHE_BUST =
  document.currentScript?.src?.split('v=')[1]?.split('&')[0] || Date.now();
let translations = {};
let currentLang = 'pl';

async function loadLanguage(lang) {
  if (!SUPPORTED_LANGS.includes(lang)) lang = 'pl';
  if (!translations[lang]) {
    const res = await fetch(`/static/i18n/${lang}.json?v=${I18N_CACHE_BUST}`);
    if (!res.ok) throw new Error(`i18n load failed: ${lang} (${res.status})`);
    translations[lang] = await res.json();
  }
  currentLang = lang;
  localStorage.setItem('netdash_lang', lang);
  document.documentElement.lang = lang;
  return translations[lang];
}

function t(key, vars = {}) {
  let str = translations[currentLang]?.[key] || translations.pl?.[key] || key;
  Object.entries(vars).forEach(([k, v]) => {
    str = str.replace(`{${k}}`, v);
  });
  return str;
}

const API_ERROR_MAP = {
  'Błędny login lub hasło': 'login.error',
  'Nieprawidłowe dane logowania': 'login.error',
  'Błędne aktualne hasło': 'settings.password.error.wrong',
  'Nieprawidłowy format pliku kopii zapasowej': 'settings.backup.error.invalidFormat',
  'Serwis nie znaleziony': 'error.serviceNotFound',
  'Klucz nie znaleziony': 'error.keyNotFound',
  'Notatka nie znaleziona': 'error.noteNotFound',
  'Skanowanie już trwa — poczekaj na zakończenie': 'error.scanInProgress',
  'Skan nie znaleziony': 'error.scanNotFound',
  'WoL nie jest skonfigurowane dla tego serwisu': 'error.wolNotConfigured',
  'Sleep-on-LAN nie jest skonfigurowane dla tego serwisu': 'error.solNotConfigured',
  'Skan ARP jest wyłączony w ustawieniach': 'error.arpDisabled',
  'Aktualizacja z portalu wymaga docker.sock — na QNAP użyj Watchtower lub Pull w Container Station': 'error.updateApplyUnavailable',
  'Aktualizacja z portalu wymaga docker.sock — bez niego użyj Watchtower lub ręcznego pull obrazu': 'error.updateApplyUnavailable',
  'Aktualizacja z poziomu aplikacji jest wyłączona (brak docker.sock lub NETDASH_UPDATE_APPLY_ENABLED)': 'error.updateApplyUnavailable',
};

function translateApiDetail(detail) {
  if (!detail || typeof detail !== 'string') return detail;
  const exact = API_ERROR_MAP[detail];
  if (exact) return t(exact);
  if (detail.startsWith('Nieobsługiwana wersja kopii zapasowej:')) {
    const version = detail.slice('Nieobsługiwana wersja kopii zapasowej:'.length).trim();
    return t('error.backupUnsupportedVersion', { version });
  }
  if (detail.startsWith('Nie udało się wysłać pakietu WoL:')) return t('action.wolFailed');
  if (detail.startsWith('Nie udało się wysłać pakietu SOL:')) return t('action.sleepFailed');
  if (detail.startsWith('Skan ARP nie powiódł się:')) return t('settings.arpScan.failed');
  return detail;
}

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.dataset.i18n;
    const attr = el.dataset.i18nAttr;
    const text = t(key);
    if (attr) el.setAttribute(attr, text);
    else el.textContent = text;
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll('[data-i18n-title]').forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
}
