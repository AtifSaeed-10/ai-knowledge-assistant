import type { Config } from "tailwindcss";

const config = {
  darkMode: ["class"],

  content: [
    "./src/**/*.{ts,tsx}",
  ],

  prefix: "",

  theme: {

    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },


    extend: {

      colors: {

        brand: {
          app: "rgb(var(--bg-app) / <alpha-value>)",
          surface: "rgb(var(--bg-surface) / <alpha-value>)",
          olive: "rgb(var(--accent-olive-deep) / <alpha-value>)",
          sage: "rgb(var(--accent-sage) / <alpha-value>)",
          muted: "rgb(var(--text-muted) / <alpha-value>)",
        },


        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",

        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",


        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },


        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },


        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },


        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },

      },


      boxShadow: {

        "lg-floating":
          "0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)",

        "ai-glow":
          "0 0 15px rgba(74,93,35,0.15)",

      },


      fontFamily: {

        sans: [
          "var(--font-jakarta)",
          "sans-serif",
        ],

      },

    },

  },


  plugins: [
    require("tailwindcss-animate"),
  ],

} satisfies Config;


export default config;