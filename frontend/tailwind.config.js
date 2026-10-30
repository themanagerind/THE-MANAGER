/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Design plan (frontend-design skill): navy + white civic palette,
        // muted gold accent — deliberately NOT a bright SaaS teal/purple or
        // the generic terracotta (#D97757) tell.
        navy: {
          DEFAULT: "#0A1F44", // primary — locked by brief
          light: "#14315C", // secondary/hover
          muted: "#3A4E6E", // disabled/tertiary text on white
        },
        paper: "#FBFBFA", // off-white content background — distinct from pure white chrome
        gold: {
          DEFAULT: "#B8873A", // status/CTA accent — official, not decorative
          light: "#D9B876",
        },
        ink: "#1C2430", // body text — near-black, not pure #000
        line: "#E3E6EB", // hairline dividers, used instead of card shadows
        success: "#2F7A4D",
        warning: "#B8873A",
        danger: "#A8432F",
      },
      fontFamily: {
        // Public Sans — civic/government association fits a society
        // management app better than a generic SaaS geometric sans.
        sans: ["Public Sans", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "6px", // small, consistent — not the uniform rounded-card kit
      },
      boxShadow: {
        none: "none", // structural dividers preferred over shadow-cards
      },
    },
  },
  plugins: [],
};
