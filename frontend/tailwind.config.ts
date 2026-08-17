import type { Config } from "tailwindcss";

const config = {
  content: ["./src/**/*.{ts,tsx}"],

  theme: {
    extend: {
      colors: {
        paper: "#F6F7F4",

        surface: {
          DEFAULT: "#FFFFFF",
          muted: "#FBFBFA",
          sunken: "#F1F3EF",
        },

        line: {
          DEFAULT: "#EBEFEA",
          strong: "#DCE2D9",
        },

        /* Text colours are AA-compliant on paper and surface backgrounds. */
        ink: {
          DEFAULT: "#1C241F",
          soft: "#2A322E",
          muted: "#5B6858",
          subtle: "#63705F",
          icon: "#7C8877",
        },

        olive: {
          DEFAULT: "#4A5D23",
          dark: "#3E4E1D",
          soft: "#EFF1EC",
        },

        sage: {
          DEFAULT: "#87AB72",
          soft: "#C5D4B8",
        },

        danger: {
          DEFAULT: "#B42318",
          dark: "#912018",
          soft: "#FEF3F2",
          line: "#F6D6D2",
        },

        warn: {
          DEFAULT: "#8A6D1F",
          soft: "#FBF7EA",
          line: "#EADFC0",
        },
      },

      fontFamily: {
        sans: ["var(--font-jakarta)", "system-ui", "sans-serif"],
      },

      /* One scale, used everywhere. Nothing smaller than 11px, and 11px is
         reserved for uppercase section labels. */
      fontSize: {
        label: ["0.6875rem", { lineHeight: "1rem" }],
        meta: ["0.75rem", { lineHeight: "1.125rem" }],
        ui: ["0.8125rem", { lineHeight: "1.25rem" }],
        body: ["0.875rem", { lineHeight: "1.5rem" }],
        answer: ["0.9375rem", { lineHeight: "1.65" }],
        title: ["1rem", { lineHeight: "1.5rem" }],
        h2: ["1.125rem", { lineHeight: "1.6rem" }],
        h1: ["1.25rem", { lineHeight: "1.75rem" }],
        display: ["1.75rem", { lineHeight: "2.125rem" }],
      },

      boxShadow: {
        card: "0 1px 2px rgba(28, 36, 31, 0.05)",
        raised: "0 8px 24px -8px rgba(28, 36, 31, 0.12)",
        overlay: "0 24px 48px -16px rgba(28, 36, 31, 0.24)",
      },

      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "rise-in": {
          from: { opacity: "0", transform: "translate3d(0, 4px, 0)" },
          to: { opacity: "1", transform: "translate3d(0, 0, 0)" },
        },
        "slide-in-right": {
          from: { opacity: "0", transform: "translate3d(8px, 0, 0)" },
          to: { opacity: "1", transform: "translate3d(0, 0, 0)" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
        "progress-slide": {
          from: { transform: "translateX(-100%)" },
          to: { transform: "translateX(220%)" },
        },
      },

      animation: {
        "fade-in": "fade-in 200ms ease-out both",
        "rise-in": "rise-in 240ms ease-out both",
        "slide-in-right": "slide-in-right 200ms ease-out both",
        shimmer: "shimmer 1.8s linear infinite",
        "progress-slide": "progress-slide 1.6s ease-in-out infinite",
      },
    },
  },

  plugins: [],
} satisfies Config;

export default config;
