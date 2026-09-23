/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";

// Section 37 (PWA production requirements): service worker, manifest, icon
// sizes, navy theme color, offline fallback, background sync for offline
// "Paid" submission (queued via the outbox pattern in src/api/offlineQueue.ts).
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.png", "apple-touch-icon.png", "logo.png"],
      manifest: {
        name: "Housing Society Manager",
        short_name: "Society",
        description: "Manage your housing society — dues, complaints, visitors, notices.",
        theme_color: "#0A1F44",
        background_color: "#FFFFFF",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // stale-while-revalidate for API GETs, cache-first for static assets
        // (Section 37) — navigation fallback keeps the app shell available
        // offline; API calls are excluded from the precache (handled by the
        // offline outbox in src/api/offlineQueue.ts for writes, and simply
        // fail gracefully for reads). Caches are cleared on every
        // login/logout (src/auth/AuthContext.tsx) so stale-while-revalidate
        // never shows one user's cached data to the next on a shared device.
        navigateFallback: "/index.html",
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/.*\/api\/v1\/(notices|amenities)(\?.*)?$/,
            handler: "StaleWhileRevalidate",
            options: { cacheName: "api-read-cache", expiration: { maxEntries: 50, maxAgeSeconds: 3600 } },
          },
        ],
      },
    }),
  ],
  server: {
    host: true,
    port: 3000,
    allowedHosts: true,
    proxy: {
      // Default matches the backend's own default port (`uvicorn
      // app.main:app --reload`, no --port flag, per CLAUDE.md's Common
      // commands) — override with VITE_API_PROXY_TARGET if the backend
      // runs elsewhere.
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
      // Payment-proof files served by the backend's StaticFiles mount
      // (app/main.py) — same origin as /api in production too; whatever
      // reverse proxy routes /api/v1/* to the backend must also route
      // /uploads/* there.
      "/uploads": {
        target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
});
