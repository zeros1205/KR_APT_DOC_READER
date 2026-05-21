import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173
  },
  build: {
    target: "es2022",
    sourcemap: false,
    cssMinify: true,
    reportCompressedSize: true,
  },
  esbuild: {
    drop: ["console", "debugger"],
    legalComments: "none",
  },
});
