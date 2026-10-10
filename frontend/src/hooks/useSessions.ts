/** TanStack Query hooks for server state (REST). WS state lives in liveStore. */

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { calibrationApi } from "@/api/calibration";
import { sessionApi } from "@/api/session";
import type { CalibrationPayload } from "@/api/types";

/** History-list data: lightweight per-session summaries (metadata + dominant
 * state computed server-side). One round trip - no per-row export fetch. */
export function useSessions() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: sessionApi.summaries,
  });
}

export function useSessionDetail(sessionId: string | undefined) {
  return useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => sessionApi.exportData(sessionId!, "json"),
    enabled: !!sessionId,
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => sessionApi.remove(sessionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

export function useCalibration() {
  return useQuery({
    queryKey: ["calibration"],
    queryFn: calibrationApi.get,
  });
}

export function useSetCalibration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CalibrationPayload) => calibrationApi.set(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calibration"] }),
  });
}

export function useClearCalibration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => calibrationApi.clear(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["calibration"] }),
  });
}
