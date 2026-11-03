/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0f0f13",
          card: "#18181f",
          "card-hover": "#1e1e28",
        },
        border: {
          DEFAULT: "#2a2a35",
          light: "#3a3a48",
        },
        accent: {
          DEFAULT: "#7c3aed",
          light: "#8b5cf6",
          hover: "#6d28d9",
        },
        text: {
          primary: "#f1f1f5",
          secondary: "#9ca3af",
          muted: "#6b7280",
        },
        status: {
          supported: "#22c55e",
          contradicted: "#ef4444",
          insufficient: "#f59e0b",
          error: "#f97316",
        },
      },
    },
  },
  plugins: [],
};
