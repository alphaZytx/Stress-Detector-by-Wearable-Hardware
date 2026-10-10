/**
 * Settings store - user preferences, persisted to localStorage. Read by the Live
 * view (which sensors to show, buffer length) and the breathing auto-trigger.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemeMode = "light" | "dark";

export interface SensorVisibility {
  hr: boolean;
  gsr: boolean;
  temp: boolean;
}

interface SettingsState {
  theme: ThemeMode;
  sensors: SensorVisibility;
  /** Rolling sample buffer length for the Live view, in seconds. */
  bufferSeconds: number;
  /** P(stress) threshold for the breathing auto-trigger prompt. */
  stressThreshold: number;
  /** Apply per-user calibration to new recording sessions (opt-in per session). */
  useCalibration: boolean;
  /** Demo mode replays the canned session instead of connecting to the WS. */
  demoMode: boolean;

  setTheme: (t: ThemeMode) => void;
  toggleTheme: () => void;
  setSensor: (key: keyof SensorVisibility, on: boolean) => void;
  setBufferSeconds: (s: number) => void;
  setStressThreshold: (t: number) => void;
  setUseCalibration: (on: boolean) => void;
  setDemoMode: (on: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: "light",
      sensors: { hr: true, gsr: true, temp: true },
      bufferSeconds: 60,
      stressThreshold: 0.7,
      useCalibration: true,
      demoMode: false,

      setTheme: (theme) => set({ theme }),
      toggleTheme: () =>
        set((s) => ({ theme: s.theme === "light" ? "dark" : "light" })),
      setSensor: (key, on) =>
        set((s) => ({ sensors: { ...s.sensors, [key]: on } })),
      setBufferSeconds: (bufferSeconds) => set({ bufferSeconds }),
      setStressThreshold: (stressThreshold) => set({ stressThreshold }),
      setUseCalibration: (useCalibration) => set({ useCalibration }),
      setDemoMode: (demoMode) => set({ demoMode }),
    }),
    { name: "stress-settings" },
  ),
);
