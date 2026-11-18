import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` opens the UI in a browser against tools/dev_backend.py (no 3ds Max needed).
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { port: 5173, proxy: { "/call": "http://127.0.0.1:8799" } },
  build: { outDir: "dist", emptyOutDir: true },
});
