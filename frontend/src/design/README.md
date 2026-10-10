# Design System - "Neo-Brutalist" (2026-06-19 redesign, anti-AI-slop)

One unified brutalist visual language across every screen: **flat blocks of
color, thick 2px ink borders, sharp corners, hard OFFSET shadows** (e.g.
`4px 4px 0 0 ink`) that snap shut on press, bold Space Grotesk display +
monospace labels, on an **engineering-grid paper** background. No gradients, no
glass, no blur - confident, raw, intentional.

> Replaces the earlier glass-aurora system. The historical token *names*
> (`--clinical-*`, `--wellness-*`) are retained for compatibility but now describe
> one flat brutalist palette.

## Foundations

- **Type** - display: **Space Grotesk** (bold, often UPPERCASE for headings,
  nav, buttons, badges); body: **Inter**; labels/eyebrows: **JetBrains Mono**,
  uppercase, wide-tracked; numerics: tabular (`.tnum`, display font).
- **Background** - flat engineering grid (`repeating-linear-gradient` 32px lines)
  on paper (`#f3f1ea`) / near-black (`#0b0b0c`). Fixed. No drifting blooms.
- **Surfaces** (`index.css`): all flat -
  - `.surface-card` - solid fill + **2px ink border** + hard offset shadow.
  - `.surface-raised` - hero surface, deeper hard shadow.
  - `.surface-glass` - same flat brutalist treatment (name kept for compat).
- **Color** - accent = electric blue (`#0047ff` / dark `#5b82ff`), used flat on
  primary buttons, nav-active, switches, slider, icon chips. Stress state:
  calm/baseline = green, moderate = orange, high = red - solid fills.
- **Radii** - 0 everywhere (`--radius-*` = 0; `2xl` = 2px). **Shadows** are hard
  offsets, never soft. **Motion** is snappy (120–180ms).
- **Interaction** - bordered buttons/inputs use the brutalist press: hover lifts
  by translating `-2px,-2px` (shadow grows); active snaps to `0,0` shadow-none.

## Layouts

- **Live** - bento command center: radial **StressDial** (flat arc, hard caps,
  color = stress level, top accent bar) anchors a 12-col grid; HR waveform + HRV
  proxy stack beside it; HR/GSR/Temp/Motion vital tiles below; recording bar
  spans the bottom. Below that, the **input inspector** (`ModelInputPanel`) with
  a header switch between two views of what feeds the classifier:
  **Model input** (pipeline strip + the live 18-feature vector, grouped by sensor
  family, filterable/sortable/expandable) and **Raw sensors**
  (`RawSensorStream`: a **serial monitor** - 1 Hz packets printing to a live
  console, newest at the bottom, blinking caret, tail-follow that detaches when
  you scroll back, aligned/csv/json output modes, copy + clear, and click-a-line
  for the full packet). That console keeps a fixed dark palette in both themes:
  it is a terminal, and re-tinting it for light mode would cost the legibility
  that makes it read as a live wire. **Freeze** holds both streams so the mode
  can be switched on a single instant.
- **Auth** - centered card on the grid plane, square accent brand mark, mono
  field labels, biosignal line.
- **History** - grid of bordered session cards (title, date, dominant badge,
  duration, notes, `⋮` actions).
- **SessionDetail** - metadata chips + timeline-led bento with a stats column.
- **Settings** - Calibration is a full-width hero (accent top bar); the rest is
  an **equal-height** two-column block grid (`grid lg:grid-cols-2`, default
  stretch so paired cards match height - no ragged gaps).
- **Calibration / Breathing** - full-screen flows on the grid plane. The
  breathing guide is a single **thick-bordered disc** that scales with the breath
  over a dashed reference ring (the old conic `LuminousOrb` was removed).

## Navigation

- Sidebar is a **hamburger-collapsible drawer** (`AppShell` holds `open` state):
  on `lg` it sits in flow and pushes content; on small screens it overlays with a
  backdrop. A collapse button lives in the sidebar header; when closed, a
  floating hamburger (top-left, on every route) reopens it.

## Dark mode - "Quiet Dark" (not inverted brutalism)

Dark mode is a **different system on purpose**, because inverting brutalism
failed on its own terms: pure-white 2px borders on near-black put the brightest
pixels of the screen on every container edge (glare), and the hard *black*
offset shadows were invisible on a black canvas, so elevation disappeared and
every surface flattened into one plane.

- **Canvas** - deep blue-slate `#0e1116` (never pure black: it maximises
  halation against bright text), with a near-invisible grid (1.8% alpha) and one
  soft overhead wash so the plane has a light source.
- **Depth** - from **layered surfaces** (`bg #0e1116` → `surface #151a21` →
  `surface-2 #1c222b`, ~+4% lightness per step) plus soft ambient shadows and a
  1px inset top highlight (`--ring-highlight`). Borders no longer carry
  elevation.
- **Borders** - hairline white at **9%** (strong: 17%), **1px** not 2px.
- **Radii** - soften (`--radius-md` 8px, `2xl` 16px): hairlines + sharp corners
  read as unfinished.
- **Type** - off-white `#e7ecf3`, never `#fff`.
- **Accent** - desaturated azure `#5b8cff`; state colors soften to
  `#3ecf8e` / `#f0a43a` / `#f2686f` so they sit on the ground instead of
  vibrating against it.
- **Wellness panels** get real frosted glass in dark (`.surface-glass`), with a
  solid-fill fallback where `backdrop-filter` is unsupported.

Light mode keeps the brutalist system **unchanged**.

## How it's wired

- `tokens.css` = CSS variables (+ `[data-theme="dark"]`). `tailwind.config.ts`
  maps them to utilities. `tokens.ts` exposes `stressLevel` / `cssVar` for
  Recharts strokes. Dark mode toggles `[data-theme]` on `<html>`.
- Border *width* and `rounded-none` are baked into ~30 component class lists, so
  dark-mode **structural** overrides (`.border-2` → 1px, `.rounded-none` →
  soft, surface treatments, focus ring, scrollbars) live in `index.css` under
  `[data-theme="dark"]` rather than forking every component.

## Accessibility

- Stress always pairs color with a text label (`BASELINE` / `STRESS`); dial is
  `role="status"` + `aria-live`. 4.5:1+ contrast in both themes. Chunky 3px
  focus ring. Icon-only buttons carry `aria-label`. All motion respects
  `prefers-reduced-motion`.

## Dead code

`components/wellness/LuminousOrb.tsx` and `components/live/StressIndicator.tsx`
are no longer imported (superseded by the brutalist BreathingCircle and
StressDial); kept on disk but tree-shaken out of the bundle.
