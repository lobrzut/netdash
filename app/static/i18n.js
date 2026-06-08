const SUPPORTED_LANGS = ['pl', 'en', 'de', 'uk'];
let translations = {};
let currentLang = 'pl';

async function loadLanguage(lang) {
  if (!SUPPORTED_LANGS.includes(lang)) lang = 'pl';
  if (!translations[lang]) {
    const res = await fetch(`/static/i18n/${lang}.json`);
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
}
