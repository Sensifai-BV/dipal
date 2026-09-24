import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath } from "url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  base: "/",
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "@core": fileURLToPath(new URL("./src/core", import.meta.url)),
      "@auth": fileURLToPath(new URL("./src/auth", import.meta.url)),
      "@module": fileURLToPath(new URL("./src/module", import.meta.url)),
    },
  },
  server: {
    port: 3000,
    watch: {
      followSymlinks: false,
    },
  },
  build: {
    sourcemap: true,
    rollupOptions: {
      input: fileURLToPath(new URL("./index.html", import.meta.url)),
      output: {
        format: "es",
        dir: "dist",
        sourcemap: "inline",
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
  preview: {
    port: 5000,
    open: true,
  },
});
