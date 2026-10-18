import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGUAGES } from "@/i18n";

/** Dashboard-chrome language picker (Resident/Admin/Sub-admin — see
 * AppShell's LANGUAGE_SWITCHER_ROLES). Persists via i18next-browser-
 * languagedetector's localStorage cache (src/i18n/index.ts), so the choice
 * survives reloads/future sessions on the same device without any backend
 * call — this is a display-language preference, not account data.
 * Rendered in the same two spots as RoleSwitcher (mobile dropdown menu,
 * desktop top-right overlay), so it follows the same dual-context styling:
 * white text/transparent bg on the dark mobile menu, navy text/white bg on
 * the light desktop header area.
 *
 * No `normal-case` override here even though AppShell force-uppercases its
 * whole subtree (including form controls — see AppShell's own comment):
 * `text-transform: uppercase` is a no-op on scripts with no case concept
 * (Devanagari, Gujarati, Tamil, Telugu, Bengali, Odia — 7 of these 8
 * options), so only "English" is actually affected, and shouting-case
 * matches every other label in this dashboard rather than looking like an
 * inconsistent exception. */
export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();

  return (
    <label className="flex items-center gap-2 text-sm text-white/90 md:text-navy">
      <span className="sr-only md:not-sr-only md:text-navy-muted">{t("common.language")}</span>
      <select
        value={i18n.resolvedLanguage ?? "en"}
        onChange={(e) => void i18n.changeLanguage(e.target.value)}
        className="bg-transparent md:bg-white md:border md:border-line rounded px-2 py-1 text-sm"
      >
        {SUPPORTED_LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code} className="text-ink">
            {lang.nativeName}
          </option>
        ))}
      </select>
    </label>
  );
}
