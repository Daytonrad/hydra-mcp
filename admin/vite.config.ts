import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The proxy serves the built page at /admin/. In dev, Vite proxies the API to the Python proxy.
export default defineConfig({
  base: "/admin/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/admin/api": "http://127.0.0.1:8765" },
  },
});
