/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b1220",
        card: "#111a2e",
        cardalt: "#0f1729",
        border: "#1e2a45",
        accent: "#0ea5e9",
        profit: "#22c55e",
        loss: "#ef4444",
      },
    },
  },
  plugins: [],
};
