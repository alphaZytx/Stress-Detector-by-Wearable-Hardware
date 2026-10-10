import { api } from "./client";
import type { DemoSession } from "./types";

export const demoApi = {
  // Public route - no auth header needed (demo mode works without login).
  session: () => api.get<DemoSession>("/demo/session", true),
};
