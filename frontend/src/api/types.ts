/**
 * Wire types - mirror the backend "Frontend contract" (HANDOFF.md). Keep in sync.
 */

export type StressLabel = "baseline" | "stress";

export interface SensorSample {
  timestamp_ms: number;
  bpm: number | null;
  avg_bpm: number | null;
  temp_c: number | null;
  gsr: number;
  /** Display-only auxiliary readings; not supplied to the WESAD classifier. */
  spo2?: number | null;
  ambient_temp_c?: number | null;
  ir?: number | null;
  finger_present?: boolean | null;
  source_label: string | null;
}

/** 18 features, in canonical order (see features/schema.py). */
export interface FeatureVector {
  hr_mean: number;
  hr_std: number;
  hr_min: number;
  hr_max: number;
  hr_range: number;
  hr_slope: number;
  hr_pnn_proxy: number;
  gsr_mean: number;
  gsr_std: number;
  gsr_min: number;
  gsr_max: number;
  gsr_range: number;
  gsr_slope: number;
  gsr_auc: number;
  gsr_peaks: number;
  temp_mean: number;
  temp_std: number;
  temp_slope: number;
}

/** Which classifier the service is serving (inference.model_type). */
export type ModelType =
  | "svm"
  | "random_forest"
  | "xgboost"
  | "mlp"
  | "soft_voting"
  | "stacking";

export interface Prediction {
  timestamp_ms: number;
  label: StressLabel;
  confidence: number;
  smoothed_label: StressLabel;
  smoothed_confidence: number;
  raw_proba: { baseline: number; stress: number };
  calibration_applied: boolean;
  /** Added with the ensemble work. Optional so older payloads still parse. */
  model_type?: ModelType | string;
  /** Per-base-model P(stress). Present only when an ensemble is serving. */
  base_probabilities?: Record<string, number> | null;
}

/** WebSocket envelope. Server→client only. */
export type WsMessage =
  | { type: "sample"; data: SensorSample }
  | { type: "features"; data: FeatureVector; timestamp_ms: number | null }
  | { type: "prediction"; data: Prediction };

/* ---- auth ---- */
export interface UserInfo {
  user_id: string;
  email: string;
  display_name: string | null;
  created_at_ms: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_at_ms: number;
  user: UserInfo;
}

/* ---- sessions ---- */
export interface SessionInfo {
  session_id: string;
  started_at_ms: number;
  ended_at_ms: number | null;
  user_label: string | null;
  notes: string | null;
  user_id: string | null;
}

/** Lightweight History-list row: metadata + server-computed dominant state.
 * Lets History render the per-session badge without an export fetch per row. */
export interface SessionSummary {
  session_id: string;
  started_at_ms: number;
  ended_at_ms: number | null;
  user_label: string | null;
  notes: string | null;
  dominant_state: StressLabel | null;
  dominant_state_pct: number;
}

export interface SessionLabel {
  session_id: string;
  timestamp_ms: number;
  label: string;
}

export interface SessionExport {
  session_id: string;
  started_at_ms: number;
  ended_at_ms: number | null;
  user_label: string | null;
  notes: string | null;
  samples: SensorSample[];
  predictions: SessionPredictionRow[];
  labels: SessionLabel[];
}

/** Persisted prediction row shape (from the DB, slightly flatter than Prediction). */
export interface SessionPredictionRow {
  session_id: string;
  timestamp_ms: number;
  label: StressLabel;
  confidence: number;
  smoothed_label: StressLabel;
  smoothed_confidence: number;
  p_baseline: number;
  p_stress: number;
}

/* ---- calibration ---- */
export interface CalibrationInfo {
  calibrated: boolean;
  user_id: string;
  gsr_baseline: number | null;
  hr_baseline: number | null;
  temp_baseline: number | null;
  captured_at_ms: number | null;
}

export interface CalibrationPayload {
  hr_baseline?: number | null;
  gsr_baseline?: number | null;
  temp_baseline?: number | null;
  extra?: Record<string, unknown>;
}

/* ---- demo ---- */
export interface DemoEvent {
  t_s: number;
  phase: "baseline" | "stress" | "breathing";
  narration: string;
}

export interface DemoSession {
  session_id: "DEMO";
  duration_s: number;
  events: DemoEvent[];
  samples: SensorSample[];
  /** Feature emits, each tagged with timestamp_ms (aligned to predictions). */
  features: (FeatureVector & { timestamp_ms: number })[];
  predictions: Prediction[];
}
