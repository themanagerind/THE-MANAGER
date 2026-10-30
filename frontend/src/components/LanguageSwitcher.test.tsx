import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@/i18n";
import i18n from "@/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { SUPPORTED_LANGUAGES } from "@/i18n";

describe("LanguageSwitcher", () => {
  it("lists all 8 supported languages by their native name", () => {
    render(<LanguageSwitcher />);
    const select = screen.getByRole("combobox");
    expect(select.children).toHaveLength(SUPPORTED_LANGUAGES.length);
    for (const lang of SUPPORTED_LANGUAGES) {
      expect(screen.getByRole("option", { name: lang.nativeName })).toBeInTheDocument();
    }
  });

  it("switches the active i18next language and re-renders translated nav-style text", async () => {
    const user = userEvent.setup();
    await i18n.changeLanguage("en");
    render(<LanguageSwitcher />);

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("en");

    await user.selectOptions(select, "hi");
    expect(i18n.language).toBe("hi");
    // The translated label for this component's own "Language" string —
    // confirms changeLanguage actually took effect app-wide, not just the <select>'s own value.
    expect(await screen.findByText(i18n.t("common.language", { lng: "hi" }))).toBeInTheDocument();
  });

  it("persists the choice to localStorage (survives reload) via the language detector's cache", async () => {
    const user = userEvent.setup();
    await i18n.changeLanguage("en");
    render(<LanguageSwitcher />);

    await user.selectOptions(screen.getByRole("combobox"), "ta");
    expect(localStorage.getItem("i18nextLng")).toBe("ta");
  });
});
