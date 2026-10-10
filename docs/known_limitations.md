# Known Limitations

Honest record of what does **not** work cleanly, gathered during Phase 4.3
end-to-end testing. A viva examiner asking "what if X" should get a documented
answer here rather than a surprise. Items are grouped: ✅ verified-good,
⚠️ limitation (documented, not fixed), 🔧 fixed during 4.3.

## Connection / reconnection

- ✅ **Backend restart mid-session.** Killing the backend during a live session
  escalates the connection pill `Connected → Reconnecting… → Disconnected` (after
  a 5 s grace), and on backend restart it returns to `Connected` automatically
  (WebSocket exponential backoff, 1→30 s). Verified: `tests/e2e_reconnect.mjs`.
- ⚠️ **Recording state is lost on page refresh (mid-session).** The recording
  store (`useRecording`) is in-memory (not persisted). The **backend** keeps the
  session active (`runtime._active_session`), but after a refresh the UI shows
  "Start recording" again and can't Stop the still-active session from the button.
  There is no `GET /session/active` endpoint to rehydrate. **Workaround:** the
  session is still recorded correctly server-side and appears in History; to end
  it, start+stop a new session (stop targets the active session) or restart the
  backend. **Future:** add `GET /session/active` and rehydrate the store on load.
- ⚠️ **Slow network (WS throttled to slow-3G).** Gauges update late and in bursts
  but the dashboard does not crash; rAF easing keeps the UI responsive. Not a
  show-stopper for the demo (local loopback), documented for completeness.

## Authentication

- ✅ **Invalid / expired token.** A bad or expired JWT in `localStorage` is
  rejected: `ProtectedRoute` (client-side expiry decode) redirects to `/login`,
  and the WS closes with code 4401 (terminal, no reconnect loop). REST returns
  401 for an invalid token. Verified: `tests/e2e_failure_modes.mjs` + API probe.
- ⚠️ **No production auth hardening.** JWT secret falls back to a dev value with
  a loud warning if `STRESS_JWT_SECRET` is unset; no refresh tokens, rate
  limiting, password-strength rules, or HTTPS enforcement. Acceptable for a viva
  demo on localhost; **not** production-ready. (Pre-existing, documented since 3.0.)

## Empty / edge states

- ✅ **Brand-new user.** `/history` shows a deliberate empty state ("No sessions
  yet" + CTA); `/settings` shows "Not calibrated". Verified: `e2e_failure_modes.mjs`.
- ✅ **Nonexistent session detail.** `/history/<bad-id>` renders a graceful
  "Failed to load session." message (export 404 → query error), no crash/blank.
- ✅ **Demo mode.** Toggling demo mode replays the canned session; recording is
  disabled and the pill shows "Demo mode" (see Phase 4.4).

## Bug sweep (4.3.c)

- ✅ **Double registration (same email).** Second `POST /auth/register` returns
  409, surfaced as a form error - one user created, not two. (API probe.)
- ✅ **Double "Start recording".** `useRecording` sets a `busy` flag for the
  duration of the start mutation, so a rapid second start is ignored - one
  session is created.
- ✅ **Nonexistent session export.** `GET /session/<bad>/export` → 404 (unit +
  API). `DELETE` of a missing/already-deleted session → 404.
- ⚠️ **Long labels / notes / display names.** Session-card title and notes use
  `truncate` (single-line ellipsis) and the card grid is fixed-width, so very
  long values clip rather than overflow the layout. Extremely long unbroken
  strings (no spaces) in notes rely on truncation; no hard `max-length` is
  enforced on the inputs. Cosmetic, not breaking.
- ⚠️ **Light mode.** A light theme exists via CSS-var tokens and the theme toggle.
  The neo-brutalist redesign was tuned primarily in its default palette; light
  mode renders correctly but has had less visual QA. No layout breakage observed.

## Data / model (carried from earlier phases, restated for the viva)

- ⚠️ **WESAD-only model does not transfer to project hardware** (predicts 0%
  stress on project CSVs); per-user calibration does not fix it. The **combined
  v2** model is deployed. See HANDOFF "CRITICAL FINDING" and
  `scripts/check_model_transfer.py`.
- ⚠️ **Calibration is a heuristic**, not validated domain adaptation (subtracts
  per-user resting baselines before the scaler). May help or hurt per user;
  opt-in per session.
- ⚠️ **Single project subject.** The "PROJECT" LOSO fold is 102 windows vs
  ~350/subject for WESAD - a ~3.5× weaker estimate for the deployment-relevant fold.
- ⚠️ **GSR unit mismatch.** WESAD EDA is µS; project GSR is raw 12-bit ADC.
  StandardScaler normalises, but the distributions differ across domains.

## Ensemble / multi-model (Phase 5)

- ⚠️ **No ensemble improvement is demonstrated.** Under nested LOSO the
  ensembles lead the SVM baseline on pooled macro-F1 (soft voting 0.910,
  stacking 0.906, SVM 0.889), but a per-subject Wilcoxon signed-rank test does
  **not** separate them (p ≈ 0.28 for soft voting, 0.50 for stacking). With 16
  subjects and a ±0.13–0.19 between-subject spread, a difference this size is
  not resolvable. The correct claim is "comparable", not "better". Full
  numbers: `reports/ensemble_report.md`.
- ⚠️ **Soft voting scored marginally above the deployed stacking ensemble**
  (0.9095 vs 0.9058 pooled macro-F1). The gap is far inside the noise;
  stacking is deployed because it learns the weighting rather than assuming it,
  and it has better baseline precision and stress recall. Switching is a
  one-line config change (`inference.model_type: soft_voting`).
- ⚠️ **The PROJECT fold is hard for every model.** All six score 0.32–0.45
  macro-F1 on the project subject. This is the cross-device gap above, not a
  model-selection problem - no ensemble fixes it.
- ⚠️ **No post-hoc probability calibration.** Raw `predict_proba()` outputs are
  averaged. The report's §9 shows they sit on broadly comparable scales and
  reports Brier scores (the ensembles do improve those: 0.062–0.067 vs 0.080),
  but tree and margin models are not calibrated the same way. Adding a
  calibrator would have to be fitted inside the training folds only.
- ⚠️ **Threshold never tuned.** Stays at the application's existing
  `P(stress) ≥ 0.5` for every model.
- ⚠️ **Hyperparameter approximation inside folds.** Within an outer LOSO fold,
  hyperparameters chosen on the training subjects are reused by that fold's OOF
  clones. Selection information moves inside the training portion; it never
  reaches the held-out subject. Documented rather than hidden.
- ⚠️ **Ensemble inference costs ~17 ms/window vs 0.2 ms for the SVM**, dominated
  by the 200-tree forest. Irrelevant against a 5 s cadence (~300× headroom), but
  it would matter on an embedded target.
- ⚠️ **xgboost is an extra native dependency** (needs `libomp` on macOS). It is
  imported lazily, so the service still starts on the SVM baseline without it -
  but an ensemble artifact cannot be unpickled without it installed, and the
  loader says so explicitly rather than failing obscurely.
