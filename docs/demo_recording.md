# Demo Recording - Walkthrough Script (~3 min)

Records the **demo-mode** walkthrough (no wearable needed). Claude Code cannot
record video; follow these steps and save to `docs/demo_recording.mp4`.

## Setup (once)

```bash
# Terminal 1 - backend
cd stress-detection
python3 scripts/run_service.py        # serves :8010, model svm_combined_v2

# Terminal 2 - frontend
cd stress-detection/frontend
pnpm dev                              # http://localhost:5173
```

Open Chrome at `http://localhost:5173`. Have an account ready (register once).

## Start the screen recording

macOS: **Cmd+Shift+5** → "Record Selected Portion" (or whole screen) → Record.
Record the browser window only; ~3 minutes total.

## Walkthrough (follow in order, narrate if you like)

1. **Login** - sign in (or register) → lands on the **Live** view.
2. **Enable demo mode** - go to **Settings** → toggle **Demo mode** on.
   (Note the description switches to "Replaying the canned session.")
3. **Live view** - navigate to **Live**.
   - Point out the connection pill now reads **"Demo mode"** (distinct colour).
   - Note **Start recording** is **disabled** ("Disabled in demo mode" tooltip).
   - Let the **baseline** state settle (~first 60 s): low P(stress), calm dial.
4. **Stress transition** (~t=60–135 s) - the StressDial climbs, P(stress) rises,
   gauges (GSR/HR) move. The state flips to **stress**.
5. **Breathing banner** (~t=130 s) - the **"Stress has been elevated for a while"**
   banner appears with a **Try breathing** button. *(This is the engineered
   centrepiece - wait for it; it fires once smoothed P(stress) holds ≥0.7 for 30 s.)*
6. **Breathing exercise** - click **Try breathing** → the breathing screen.
   Run **one** breathing cycle (watch the disc expand/contract).
7. **Return to Live** - navigate back; show the **recovery** (P(stress) settling,
   dial easing back toward baseline).
8. **History** - go to **History**. Show that **no new session was recorded**
   (demo mode disables recording) - the list is unchanged.
9. **Disable demo mode** - Settings → toggle Demo mode off. Back on Live the pill
   returns to **Connected** (live stream).

## Stop the recording

Cmd+Shift+5 → Stop (or the menu-bar stop button). Save/rename to
`docs/demo_recording.mp4`.

## Tips

- The canned arc is exactly 180 s and **loops**; if you miss the banner, wait for
  the next loop (it re-fires after stress subsides and rises again).
- For a placement-interview cut, trim to: baseline → stress → banner → breathing →
  recovery (steps 3–7), ~90 s.
- Demo mode runs entirely from `data/demo/canned_session.json` - no wearable, no
  network beyond localhost. Safe to record anywhere.
