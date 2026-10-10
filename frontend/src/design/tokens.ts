/**
 * Typed re-exports of the design tokens for use in TS (e.g. Recharts colors,
 * which can't read CSS variables at config time in all cases).
 *
 * These MUST stay in sync with tokens.css. Where a component can read a CSS
 * variable directly (className, inline style), prefer that. Use these constants
 * only where a raw string is required (chart `stroke`/`fill` props read at
 * render time can use getComputedStyle, but these are a stable fallback).
 */

export type StressLevel = "calm" | "moderate" | "high";

/** Resolve a CSS variable from :root at runtime (respects current theme). */
export function cssVar(name: string): string {
  if (typeof window === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Stress-level → semantic color token name. */
export const STRESS_VAR: Record<StressLevel, string> = {
  calm: "--clinical-success",
  moderate: "--clinical-warning",
  high: "--clinical-danger",
};

/** Wellness aurora ramp (cyan → teal → emerald) for gradient stops in charts. */
export const WELLNESS_RAMP = [
  "--wellness-accent",
  "--wellness-accent-2",
  "--wellness-accent-3",
] as const;

/** Map a P(stress) probability to a stress level for color coding. */
export function stressLevel(pStress: number): StressLevel {
  if (pStress >= 0.7) return "high";
  if (pStress >= 0.4) return "moderate";
  return "calm";
}

export const SPACE = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  6: 24,
  8: 32,
  12: 48,
  16: 64,
} as const;

export const MOTION = {
  fast: 150,
  base: 250,
  slow: 500,
} as const;
