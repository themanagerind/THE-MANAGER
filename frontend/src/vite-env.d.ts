/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Showcase (Ecom store) host for the Resident "Shop Now" link — unset
  // until Showcase has a production domain (android/README.md has the
  // same "no live domain yet" blocker for the TWA build). ShopNowButton
  // hides itself entirely when this is unset, rather than linking anywhere.
  readonly VITE_SHOWCASE_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
