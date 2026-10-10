/**
 * Conceptual animations of what each of the four base models is doing.
 *
 * IMPORTANT - what is real and what is stylised:
 *   REAL      - every P(stress) shown. These come from the deployed models via
 *               the demo asset's `base_probabilities`, which build_demo_session.py
 *               produced by running the actual ensemble.
 *   STYLISED  - the internal geometry. The SVM's boundary position, which trees
 *               vote which way, the boosting residual bars, and the MLP's
 *               activations are all DERIVED FROM that real probability to
 *               illustrate the mechanism. They are not the model's real support
 *               vectors / real split thresholds / real weights.
 *
 * This is a deliberate choice: the point is to make the *mechanism* legible
 * ("a forest votes", "boosting corrects in sequence"), and real internals for a
 * 300-tree forest or a 64/32/16 net are unreadable at this size. Each panel
 * says so on screen, so nobody mistakes the picture for the weights.
 */

import { clamp01, stressColor } from "./primitives";

/** Deterministic pseudo-random in [0,1) so animations don't jitter per render. */
function seeded(i: number): number {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

/* ------------------------------------------------------------------ SVM -- */

/**
 * SVM: a curved decision boundary with points on either side. The boundary
 * slides as P(stress) moves, and the "current window" point sits where the
 * model placed it.
 */
export function SvmVisual({ p }: { p: number }) {
  const W = 190;
  const H = 110;
  // Boundary bends further right as stress probability rises.
  const shift = (clamp01(p) - 0.5) * 60;

  const points = Array.from({ length: 22 }, (_, i) => {
    const stress = i % 2 === 0;
    const cx = stress
      ? 105 + seeded(i) * 65
      : 20 + seeded(i + 50) * 62;
    const cy = 12 + seeded(i + 100) * (H - 24);
    return { cx, cy, stress };
  });

  const boundary = `M ${88 + shift} 0 C ${112 + shift} 30, ${64 + shift} 70, ${96 + shift} ${H}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-[110px] w-full">
      {/* margin band - the SVM's defining feature */}
      <path
        d={boundary}
        stroke="var(--clinical-accent-soft)"
        strokeWidth="22"
        fill="none"
        className="transition-all duration-700 ease-out"
      />
      <path
        d={boundary}
        stroke="var(--clinical-accent)"
        strokeWidth="2.5"
        fill="none"
        strokeDasharray="0"
        className="transition-all duration-700 ease-out"
      />
      {points.map((pt, i) => (
        <circle
          key={i}
          cx={pt.cx}
          cy={pt.cy}
          r="3.2"
          fill={
            pt.stress ? "var(--clinical-danger)" : "var(--clinical-success)"
          }
          opacity={0.5}
        />
      ))}
      {/* the current window */}
      <circle
        cx={26 + clamp01(p) * 138}
        cy={H / 2}
        r="7"
        fill={stressColor(p)}
        stroke="var(--clinical-text)"
        strokeWidth="2.5"
        className="transition-all duration-700 ease-out"
      />
      <text
        x={26 + clamp01(p) * 138}
        y={H / 2 - 12}
        textAnchor="middle"
        className="fill-clinical-text text-[9px] font-bold"
      >
        now
      </text>
    </svg>
  );
}

/* --------------------------------------------------------- RandomForest -- */

/** Random Forest: a grid of trees, each voting. Vote share tracks P(stress). */
export function ForestVisual({ p }: { p: number }) {
  const TREES = 24;
  const votingStress = Math.round(clamp01(p) * TREES);

  return (
    <div>
      <div className="grid grid-cols-8 gap-1.5">
        {Array.from({ length: TREES }, (_, i) => {
          // Deterministic order so trees flip in a stable sequence.
          const rank = seeded(i) * TREES;
          const stress = rank < votingStress;
          return (
            <svg
              key={i}
              viewBox="0 0 20 22"
              className="h-6 w-full transition-colors duration-500"
            >
              {/* tiny decision tree glyph */}
              <line x1="10" y1="3" x2="4" y2="11" stroke="currentColor" strokeWidth="1.4"
                className="text-clinical-faint" />
              <line x1="10" y1="3" x2="16" y2="11" stroke="currentColor" strokeWidth="1.4"
                className="text-clinical-faint" />
              <line x1="4" y1="11" x2="2" y2="19" stroke="currentColor" strokeWidth="1.4"
                className="text-clinical-faint" />
              <line x1="4" y1="11" x2="7" y2="19" stroke="currentColor" strokeWidth="1.4"
                className="text-clinical-faint" />
              <line x1="16" y1="11" x2="13" y2="19" stroke="currentColor" strokeWidth="1.4"
                className="text-clinical-faint" />
              <line x1="16" y1="11" x2="19" y2="19" stroke="currentColor" strokeWidth="1.4"
                className="text-clinical-faint" />
              <circle cx="10" cy="3" r="2.4"
                fill={stress ? "var(--clinical-danger)" : "var(--clinical-success)"} />
            </svg>
          );
        })}
      </div>
      <p className="tnum mt-2 text-center text-[11px] text-clinical-muted">
        <span className="font-bold text-clinical-text">{votingStress}</span>
        {" / "}
        {TREES} trees vote stress
      </p>
    </div>
  );
}

/* -------------------------------------------------------------- XGBoost -- */

/**
 * XGBoost: a left-to-right sequence of trees, each correcting the running
 * total. Bar heights show each stage's contribution shrinking - the shape
 * boosting actually has.
 */
export function BoostingVisual({ p }: { p: number }) {
  const STAGES = 9;
  const target = clamp01(p);
  // Running score converges on the target, each step adding a shrinking amount.
  let running = 0.5;
  const steps = Array.from({ length: STAGES }, (_, i) => {
    const remaining = target - running;
    const delta = remaining * 0.45;
    running += delta;
    return { i, running, delta };
  });

  const W = 190;
  const H = 92;
  const colW = W / STAGES;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-[92px] w-full">
      {/* zero / 0.5 reference */}
      <line x1="0" y1={H / 2} x2={W} y2={H / 2}
        stroke="var(--clinical-border)" strokeWidth="1.5" strokeDasharray="3 3" />
      {steps.map(({ i, running: r, delta }) => {
        const x = i * colW + 3;
        const h = Math.abs(delta) * H * 1.6;
        const y = delta >= 0 ? H / 2 - h : H / 2;
        return (
          <g key={i}>
            <rect
              x={x}
              y={y}
              width={colW - 6}
              height={Math.max(1.5, h)}
              fill={delta >= 0 ? "var(--clinical-danger)" : "var(--clinical-success)"}
              opacity={0.75}
              className="transition-all duration-500 ease-out"
            />
            <circle
              cx={x + (colW - 6) / 2}
              cy={H - r * H}
              r="2.6"
              fill="var(--clinical-accent)"
              className="transition-all duration-500 ease-out"
            />
          </g>
        );
      })}
      {/* running-score path */}
      <polyline
        points={steps
          .map(({ i, running: r }) => `${i * colW + 3 + (colW - 6) / 2},${H - r * H}`)
          .join(" ")}
        fill="none"
        stroke="var(--clinical-accent)"
        strokeWidth="2"
        className="transition-all duration-500 ease-out"
      />
      <text x="2" y="10" className="fill-clinical-faint text-[8px]">
        tree 1 → 400, each fixing the last
      </text>
    </svg>
  );
}

/* ------------------------------------------------------------------ MLP -- */

/** MLP: 22→64→32→16→2 shown compressed, with activation brightness. */
export function MlpVisual({ p }: { p: number }) {
  const layers = [6, 5, 4, 2]; // visual stand-ins for 22/64/32/16→2
  const W = 190;
  const H = 104;
  const colX = (i: number) => 22 + i * ((W - 44) / (layers.length - 1));

  const nodes = layers.map((count, li) =>
    Array.from({ length: count }, (_, ni) => {
      const y = (H / (count + 1)) * (ni + 1);
      // Activation rises with p in later layers; input layer is data-driven.
      const base = seeded(li * 13 + ni * 7);
      const act =
        li === 0 ? base : clamp01(base * (1 - p) + p * (0.55 + 0.45 * base));
      return { x: colX(li), y, act };
    }),
  );

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-[104px] w-full">
      {nodes.slice(0, -1).map((layer, li) =>
        layer.map((a, ai) =>
          nodes[li + 1].map((b, bi) => (
            <line
              key={`${li}-${ai}-${bi}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="var(--clinical-accent)"
              strokeWidth="0.8"
              opacity={0.1 + a.act * 0.35}
              className="transition-opacity duration-500"
            />
          )),
        ),
      )}
      {nodes.map((layer, li) =>
        layer.map((n, ni) => {
          const isOut = li === layers.length - 1;
          const outColor =
            ni === 1 ? "var(--clinical-danger)" : "var(--clinical-success)";
          return (
            <circle
              key={`n-${li}-${ni}`}
              cx={n.x}
              cy={n.y}
              r={isOut ? 6 : 4.5}
              fill={isOut ? outColor : "var(--clinical-accent)"}
              opacity={isOut ? (ni === 1 ? clamp01(p) * 0.85 + 0.15 : (1 - clamp01(p)) * 0.85 + 0.15) : 0.25 + n.act * 0.75}
              stroke={isOut ? "var(--clinical-text)" : "none"}
              strokeWidth="1.5"
              className="transition-opacity duration-500"
            />
          );
        }),
      )}
      <text x={colX(0) - 16} y={H - 2} className="fill-clinical-faint text-[8px]">22</text>
      <text x={colX(1) - 8} y={H - 2} className="fill-clinical-faint text-[8px]">64</text>
      <text x={colX(2) - 8} y={H - 2} className="fill-clinical-faint text-[8px]">32/16</text>
      <text x={colX(3) - 10} y={H - 2} className="fill-clinical-faint text-[8px]">out</text>
    </svg>
  );
}
