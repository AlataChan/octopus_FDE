/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-app": "#0F172A",
        "bg-surface": "#1E293B",
        "bg-muted": "#272F42",
        fg: "#F8FAFC",
        "fg-muted": "#94A3B8",
        border: "#475569",
        accent: "#22C55E",
        warning: "#FBBF24",
        destructive: "#EF4444"
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
        glow: "0 0 0 1px rgba(34, 197, 94, 0.14), 0 18px 60px rgba(0, 0, 0, 0.34)"
      }
    }
  },
  plugins: []
};
