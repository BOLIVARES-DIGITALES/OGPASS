// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  vite: {
    server: {
      proxy: {
        // Keep the browser on one origin during local development. This makes
        // Django sessions and CSRF protection behave like the deployed app.
        "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
        "/login": { target: "http://127.0.0.1:8000", changeOrigin: true },
        "/logout": { target: "http://127.0.0.1:8000", changeOrigin: true },
        "/register": { target: "http://127.0.0.1:8000", changeOrigin: true },
      },
    },
  },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
