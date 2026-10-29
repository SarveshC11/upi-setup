import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// The FastAPI service serves the built app from service/web at /ui/.
// `npm run dev` proxies API calls to a service running on port 8000.
const API_PATHS = ["/health", "/policy", "/score", "/compare", "/simulate", "/decisions"]

export default defineConfig({
  base: "/ui/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    outDir: resolve(import.meta.dirname, "../service/web"),
    emptyOutDir: true,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Long-lived vendor chunks so a UI change does not re-download the libraries.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined
          if (id.includes("recharts") || id.includes("d3-") || id.includes("victory")) return "charts"
          if (id.includes("motion")) return "motion"
          if (id.includes("react") || id.includes("scheduler") || id.includes("radix")) return "react"
          return "vendor"
        },
      },
    },
  },
  server: {
    proxy: Object.fromEntries(API_PATHS.map((p) => [p, "http://127.0.0.1:8000"])),
  },
})
