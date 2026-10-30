import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import en from "@/i18n/locales/en.json";
import hi from "@/i18n/locales/hi.json";
import gu from "@/i18n/locales/gu.json";
import mr from "@/i18n/locales/mr.json";
import ta from "@/i18n/locales/ta.json";
import te from "@/i18n/locales/te.json";
import bn from "@/i18n/locales/bn.json";
import or from "@/i18n/locales/or.json";

// Scope (deliberately): shared dashboard chrome only (nav labels, role
// names, profile/logout) — not full page-content translation. Individual
// pages translate incrementally as they're (re)built, same pattern as the
// Resident module being the reference implementation for new pages.
export const SUPPORTED_LANGUAGES = [
  { code: "en", nativeName: "English" },
  { code: "hi", nativeName: "हिन्दी" },
  { code: "gu", nativeName: "ગુજરાતી" },
  { code: "mr", nativeName: "मराठी" },
  { code: "ta", nativeName: "தமிழ்" },
  { code: "te", nativeName: "తెలుగు" },
  { code: "bn", nativeName: "বাংলা" },
  { code: "or", nativeName: "ଓଡ଼ିଆ" },
] as const;

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      hi: { translation: hi },
      gu: { translation: gu },
      mr: { translation: mr },
      ta: { translation: ta },
      te: { translation: te },
      bn: { translation: bn },
      or: { translation: or },
    },
    fallbackLng: "en",
    supportedLngs: SUPPORTED_LANGUAGES.map((l) => l.code),
    // localStorage first (explicit user choice persists across sessions/
    // devices-with-same-profile), then browser language, then fallback —
    // never navigator-only, so a Resident who picks Tamil doesn't get reset
    // to whatever the OS/browser locale is on next visit.
    detection: { order: ["localStorage", "navigator"], caches: ["localStorage"] },
    interpolation: { escapeValue: false }, // React already escapes
  });

export default i18n;
