/* Lightweight i18n for AI Bureaucracy Navigator.
   Include this <script> BEFORE app.js or any page-specific inline script,
   since it defines the global t()/setLanguage() used by them.

   Usage in HTML:
     <span data-i18n="hero.ctaPrimary"></span>              -> textContent
     <div data-i18n-html="placeholder.text"></div>           -> innerHTML (only for trusted static strings)
     <input data-i18n-placeholder="form.agePlaceholder">     -> placeholder attr
     <span data-i18n-title="form.religionWhy">?</span>       -> title attr
     <div data-lang-mount></div>                              -> language switcher gets appended here

   Usage in JS:
     t("findings.statusEligible")
     t("checklist.neededFor", { n: 3 })   // supports {n} placeholder substitution
*/

const SUPPORTED_LANGS = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "bn", label: "বাংলা" },
  { code: "ta", label: "தமிழ்" },
  { code: "te", label: "తెలుగు" },
];

window._i18nDict = {};
window._i18nLang = "en";

function _i18nGet(obj, path) {
  return path.split(".").reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);
}

function t(key, vars) {
  let v = _i18nGet(window._i18nDict, key);
  if (v === undefined) return key;
  if (vars) {
    for (const [k, val] of Object.entries(vars)) {
      v = v.replace(new RegExp(`\\{${k}\\}`, "g"), val);
    }
  }
  return v;
}

async function _loadLocale(lang) {
  const res = await fetch(`/locales/${lang}.json`);
  if (!res.ok) throw new Error(`Missing locale: ${lang}`);
  return res.json();
}

function _applyTranslations() {
  document.documentElement.lang = window._i18nLang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    el.innerHTML = t(el.getAttribute("data-i18n-html"));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
  });
}

function _buildSwitcher() {
  const mount = document.querySelector("[data-lang-mount]");
  if (!mount) return;
  mount.innerHTML = "";
  const sel = document.createElement("select");
  sel.id = "lang-switcher";
  sel.className = "lang-switcher";
  for (const { code, label } of SUPPORTED_LANGS) {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = label;
    if (code === window._i18nLang) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.addEventListener("change", (e) => setLanguage(e.target.value));
  mount.appendChild(sel);
}

async function setLanguage(lang) {
  if (!SUPPORTED_LANGS.some((l) => l.code === lang)) lang = "en";
  window._i18nLang = lang;
  try {
    localStorage.setItem("nav_lang", lang);
  } catch (e) {
    /* storage unavailable — language just won't persist across visits */
  }
  window._i18nDict = await _loadLocale(lang);
  _applyTranslations();
  _buildSwitcher();
  document.dispatchEvent(new CustomEvent("i18n:changed", { detail: { lang } }));
}

async function initI18n() {
  let saved = null;
  try {
    saved = localStorage.getItem("nav_lang");
  } catch (e) {
    /* ignore */
  }
  const browserLang = (navigator.language || "en").slice(0, 2);
  const initial = saved || (SUPPORTED_LANGS.some((l) => l.code === browserLang) ? browserLang : "en");
  await setLanguage(initial);
}

document.addEventListener("DOMContentLoaded", initI18n);