import type { Config } from "tailwindcss";

/**
 * Tailwind theme is driven by the CSS variables defined in src/design/tokens.css.
 * Colors reference var(--token) so light/dark switch automatically via the
 * [data-theme] attribute on <html>. See src/design/README.md for the
 * two-aesthetic (clinical "Soft UI Evolution" vs wellness "Aurora UI") boundary.
 */
export default {
  darkMode: ["class", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Clinical surface family - Live, History, Settings.
        clinical: {
          bg: "var(--clinical-bg)",
          surface: "var(--clinical-surface)",
          "surface-2": "var(--clinical-surface-2)",
          border: "var(--clinical-border)",
          "border-strong": "var(--clinical-border-strong)",
          text: "var(--clinical-text)",
          muted: "var(--clinical-muted)",
          faint: "var(--clinical-faint)",
          accent: "var(--clinical-accent)",
          "accent-2": "var(--clinical-accent-2)",
          success: "var(--clinical-success)",
          warning: "var(--clinical-warning)",
          danger: "var(--clinical-danger)",
        },
        // Wellness surface family - Calibration, Breathing, stress-alert moments.
        wellness: {
          bg: "var(--wellness-bg)",
          surface: "var(--wellness-surface)",
          text: "var(--wellness-text)",
          muted: "var(--wellness-muted)",
          faint: "var(--wellness-faint)",
          accent: "var(--wellness-accent)",
          "accent-2": "var(--wellness-accent-2)",
          "accent-3": "var(--wellness-accent-3)",
          glow: "var(--wellness-glow)",
        },
      },
      backgroundImage: {
        // Prefixed "grad-" so they never collide with same-named color utilities.
        "grad-clinical-bg": "var(--clinical-bg-grad)",
        "grad-clinical-surface": "var(--clinical-surface-grad)",
        "grad-clinical-raised": "var(--clinical-surface-raised)",
        "grad-clinical-accent": "var(--clinical-accent-grad)",
        "grad-wellness-bg": "var(--wellness-bg-grad)",
        "grad-wellness-accent": "var(--wellness-accent-grad)",
      },
      fontFamily: {
        display: "var(--font-display)",
        body: "var(--font-body)",
        mono: "var(--font-mono)",
      },
      fontSize: {
        // Display scale for hero numerics - establishes typographic rhythm.
        stat: ["2.25rem", { lineHeight: "1", letterSpacing: "-0.02em" }],
        "stat-lg": ["3rem", { lineHeight: "1", letterSpacing: "-0.025em" }],
        "stat-xl": ["4rem", { lineHeight: "0.95", letterSpacing: "-0.03em" }],
        hero: ["1.75rem", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        "2xl": "var(--radius-2xl)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        card: "var(--shadow-card)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        float: "var(--shadow-float)",
        glow: "0 0 60px 8px var(--wellness-glow)",
        "glow-strong": "0 0 90px 16px var(--wellness-glow-strong)",
        "glow-accent": "0 0 40px -4px var(--clinical-accent)",
        highlight: "var(--ring-highlight)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-slow": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        // Slow aurora drift for ambient wellness backgrounds (8-12s loop).
        "aurora-drift": {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)", opacity: "0.9" },
          "50%": { transform: "translate3d(2%,-2%,0) scale(1.08)", opacity: "1" },
        },
        "aurora-drift-2": {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1.05)", opacity: "0.8" },
          "50%": { transform: "translate3d(-3%,2%,0) scale(1)", opacity: "1" },
        },
        // Gentle resting glow/pulse for the breathing circle's environment.
        "breathe-glow": {
          "0%, 100%": { opacity: "0.5", transform: "scale(1)" },
          "50%": { opacity: "0.85", transform: "scale(1.04)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        // Terminal caret - hard on/off, no fade. A blinking block cursor is the
        // single strongest "this is a live console" signal.
        "caret-blink": {
          "0%, 49%": { opacity: "1" },
          "50%, 100%": { opacity: "0" },
        },
        // A freshly-printed serial line: flashes its ground, then settles.
        "line-print": {
          from: { backgroundColor: "rgba(62, 207, 142, 0.16)" },
          to: { backgroundColor: "transparent" },
        },
        // Continuous rotation for the luminous breathing rings (light-trail look).
        "ring-rotate": {
          to: { transform: "rotate(360deg)" },
        },
        "ring-rotate-rev": {
          to: { transform: "rotate(-360deg)" },
        },
      },
      animation: {
        "fade-in": "fade-in 220ms cubic-bezier(0.16,1,0.3,1)",
        "fade-in-slow": "fade-in-slow 600ms cubic-bezier(0.16,1,0.3,1)",
        "pulse-soft": "pulse-soft 2s ease-in-out infinite",
        "aurora-drift": "aurora-drift 14s ease-in-out infinite",
        "aurora-drift-2": "aurora-drift-2 18s ease-in-out infinite",
        "breathe-glow": "breathe-glow 8s ease-in-out infinite",
        shimmer: "shimmer 2s ease-in-out infinite",
        "caret-blink": "caret-blink 1.06s steps(1, end) infinite",
        "line-print": "line-print 620ms ease-out",
      },
    },
  },
  plugins: [],
} satisfies Config;
