/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-app": "rgb(var(--bg) / <alpha-value>)",
        "bg-surface": "rgb(var(--surface) / <alpha-value>)",
        "bg-muted": "rgb(var(--muted) / <alpha-value>)",
        fg: "rgb(var(--fg) / <alpha-value>)",
        "fg-muted": "rgb(var(--fg-muted) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        warning: "rgb(var(--warning) / <alpha-value>)",
        destructive: "rgb(var(--destructive) / <alpha-value>)",
        ring: "rgb(var(--ring) / <alpha-value>)",
        primary: "rgb(var(--primary) / <alpha-value>)",
        "primary-fg": "rgb(var(--primary-fg) / <alpha-value>)"
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "\"Segoe UI\"",
          "sans-serif"
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"]
      },
      boxShadow: {
        glow: "0 0 0 1px rgb(var(--border) / 0.22), 0 18px 60px rgb(0 0 0 / 0.16)"
      }
    }
  },
  plugins: []
};
