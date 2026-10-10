/** Breathing pattern definitions. Each phase has a duration and a target scale
 * the circle animates toward (inhale → large, exhale → small, hold → stay). */

export type PhaseKind = "inhale" | "hold" | "exhale";

export interface Phase {
  kind: PhaseKind;
  seconds: number;
  label: string;
  /** Target circle scale at the END of this phase (0..1 → min..max radius). */
  target: number;
}

export interface BreathingPattern {
  id: "box" | "478" | "coherent";
  name: string;
  description: string;
  phases: Phase[];
}

const INHALE = (s: number): Phase => ({ kind: "inhale", seconds: s, label: "Breathe in", target: 1 });
const EXHALE = (s: number): Phase => ({ kind: "exhale", seconds: s, label: "Breathe out", target: 0 });
const HOLD_FULL = (s: number): Phase => ({ kind: "hold", seconds: s, label: "Hold", target: 1 });
const HOLD_EMPTY = (s: number): Phase => ({ kind: "hold", seconds: s, label: "Hold", target: 0 });

export const PATTERNS: BreathingPattern[] = [
  {
    id: "box",
    name: "Box",
    description: "4-4-4-4 · balanced calm",
    phases: [INHALE(4), HOLD_FULL(4), EXHALE(4), HOLD_EMPTY(4)],
  },
  {
    id: "478",
    name: "4-7-8",
    description: "inhale 4 · hold 7 · exhale 8",
    phases: [INHALE(4), HOLD_FULL(7), EXHALE(8)],
  },
  {
    id: "coherent",
    name: "Coherent",
    description: "5-5 · steady resonance",
    phases: [INHALE(5), EXHALE(5)],
  },
];

export const CYCLE_OPTIONS = [3, 5, 10, 0] as const; // 0 = until stopped

export function patternById(id: string): BreathingPattern {
  return PATTERNS.find((p) => p.id === id) ?? PATTERNS[0];
}
