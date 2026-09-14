import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        yana: {
          bg: "#0B0F19",
          card: "#121A29",
          border: "#1E293B",
          primary: "#38BDF8",
          secondary: "#818CF8",
          accent: "#F43F5E",
          success: "#10B981",
          warning: "#F59E0B",
          text: "#F8FAFC",
          muted: "#94A3B8",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
