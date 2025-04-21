import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      // Proxy all /api requests to the backend server
      "/api": {
        target: "http://localhost:9999",
        changeOrigin: true,
        secure: false,
        // By default, Vite proxies all /api/*, so no rewrite needed unless you want to strip /api
        // If you want to strip /api prefix, uncomment below:
        // rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/ws": {
        target: "ws://localhost:9999",
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
