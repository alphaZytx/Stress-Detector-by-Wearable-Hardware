import { api } from "./client";
import type { CalibrationInfo, CalibrationPayload } from "./types";

export const calibrationApi = {
  get: () => api.get<CalibrationInfo>("/calibration"),

  set: (payload: CalibrationPayload) =>
    api.post<{ status: string; user_id: string }>("/calibration", payload),

  clear: () => api.del<{ status: string }>("/calibration"),
};
