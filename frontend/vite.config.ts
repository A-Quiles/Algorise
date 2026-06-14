import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "Algorise — Bot de trading IA",
        short_name: "Algorise",
        description: "Bot de trading de criptomonedas con IA (modo papel).",
        theme_color: "#0ea5e9",
        background_color: "#0b1220",
        display: "standalone",
        orientation: "portrait",
        start_url: "/",
        icons: [
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" },
        ],
      },
    }),
  ],
  // host: true -> accesible desde el móvil por la IP de tu PC en la red local.
  server: { host: true, port: 5173 },
  preview: { host: true, port: 4173 },
});
