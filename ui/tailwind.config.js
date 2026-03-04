/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
      colors: {
        surface: {
          DEFAULT: "var(--surface)",
          raised: "var(--surface-raised)",
          border: "var(--surface-border)",
        },
      },
    },
  },
  plugins: [],
};
