/**
 * Explain - a standalone, no-login walkthrough of the entire inference path.
 *
 * Sensors → cleaning → 30 s window → 18 features → 4 models → ensemble →
 * smoothing → alert. Everything animates from the real deployed pipeline (see
 * usePipelineClock for why the demo asset is the data source, and
 * ModelVisuals for exactly which parts are real vs stylised).
 *
 * Deliberately NOT behind ProtectedRoute or AppShell: the point is that you
 * can hand someone the URL and they immediately see how the system works.
 */

import { FEATURE_GROUPS } from "@/explain/featureGroups";
import {
  BoostingVisual,
  ForestVisual,
  MlpVisual,
  SvmVisual,
} from "@/explain/ModelVisuals";
import {
  Flow,
  Note,
  ProbBar,
  Spark,
  Stage,
  clamp01,
  stressColor,
} from "@/explain/primitives";
import { usePipelineClock } from "@/explain/usePipelineClock";
import { BASE_MODEL_LABELS, BASE_MODEL_ORDER } from "@/lib/modelMeta";
import { Pause, Play, RotateCcw } from "lucide-react";

const MODEL_BLURB: Record<string, string> = {
  svm: "Draws one curved boundary between calm and stressed windows. Only the borderline cases shape where it sits.",
  random_forest:
    "300 decision trees, each grown on a random slice of data. The answer is the share voting “stress”.",
  xgboost:
    "400 shallow trees in sequence - each one trained to fix what the previous ones got wrong.",
  mlp: "A small neural net (64→32→16). Each layer re-mixes the 18 numbers into more abstract combinations.",
};

export function Explain() {
  const c = usePipelineClock();

  if (c.state === "loading") {
    return (
      <Centered>
        <p className="text-sm text-clinical-muted">Loading the pipeline…</p>
      </Centered>
    );
  }

  if (c.state === "error") {
    return (
      <Centered>
        <h1 className="mb-2 text-lg font-bold">Can’t reach the service</h1>
        <p className="max-w-md text-sm text-clinical-muted">
          This page reads the public demo session from the backend. Start it
          with{" "}
          <code className="bg-clinical-surface-2 px-1">
            python scripts/run_service.py
          </code>{" "}
          and reload.
        </p>
        <p className="mt-2 text-xs text-clinical-faint">{c.error}</p>
      </Centered>
    );
  }

  const s = c.latestSample;
  const f = c.features;
  const p = c.prediction;
  const pStress = p?.raw_proba.stress ?? 0;
  const smoothed = p?.smoothed_confidence ?? 0;
  const smoothedStress =
    p?.smoothed_label === "stress" ? smoothed : 1 - smoothed;

  const base = p?.base_probabilities ?? null;
  const baseVals = base
    ? BASE_MODEL_ORDER.filter((k) => k in base).map((k) => base[k])
    : [];
  const spread =
    baseVals.length > 1 ? Math.max(...baseVals) - Math.min(...baseVals) : 0;

  const windowFull = c.warmup >= 1;

  return (
    <div className="min-h-screen pb-24">
      <Header clock={c} />

      <div className="mx-auto max-w-5xl px-5">
        {/* narration ribbon */}
        {c.narration && (
          <div className="mb-6 border-2 border-clinical-border bg-clinical-surface-2 px-4 py-3">
            <p className="text-[10px] font-bold uppercase tracking-wider text-clinical-faint">
              {c.phase || "session"}
            </p>
            <p className="mt-0.5 text-sm">{c.narration}</p>
          </div>
        )}

        {/* 1 - sensors */}
        <Stage
          index={1}
          title="The wearable reads three signals"
          subtitle="One reading per second from the wrist unit. This is raw data - nothing interpreted yet."
          active
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <SensorTile
              label="Heart rate"
              unit="bpm"
              value={s?.bpm ?? null}
              series={c.samplesSoFar.slice(-60).map((x) => x.bpm ?? NaN)}
            />
            <SensorTile
              label="Skin conductance"
              unit="raw"
              value={s?.gsr ?? null}
              series={c.samplesSoFar.slice(-60).map((x) => x.gsr)}
            />
            <SensorTile
              label="Skin temp"
              unit="°C"
              value={s?.temp_c ?? null}
              series={c.samplesSoFar.slice(-60).map((x) => x.temp_c ?? NaN)}
            />
          </div>
          <Note>
            A single instant tells you almost nothing - a heart rate of 82 could
            be anything. What carries the signal is how these move{" "}
            <strong>together, over time</strong>. That’s why the next step waits.
          </Note>
        </Stage>

        <Flow label="every second" />

        {/* 2 - window */}
        <Stage
          index={2}
          title="Collect 30 seconds, then slide forward 5"
          subtitle="The model never sees one reading. It sees half a minute of history at a time."
          active={windowFull}
        >
          <WindowBar warmup={c.warmup} nextIn={c.nextEmitIn} full={windowFull} />
          <Note>
            Each new window re-uses 25 of the previous window’s 30 seconds, so a
            fresh answer arrives every 5 s instead of every 30. The cost: two
            neighbouring windows are near-duplicates - which is exactly why the
            models were tested by holding out <em>whole people</em>, never
            random rows.
          </Note>
        </Stage>

        <Flow label="every 5 seconds" active={windowFull} />

        {/* 3 - features */}
        <Stage
          index={3}
          title="Boil the window down to 18 numbers"
          subtitle="Averages, spread, trends, peak counts - one fixed list, always in the same order."
          active={!!f}
          wide
        >
          {f ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {FEATURE_GROUPS.map((g) => (
                <div key={g.title}>
                  <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-clinical-muted">
                    {g.title}
                    <span className="ml-1.5 font-normal normal-case text-clinical-faint">
                      {g.keys.length} values
                    </span>
                  </h3>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                    {g.keys.map((k) => (
                      <div
                        key={k}
                        className="flex items-baseline justify-between gap-2 border-b border-clinical-border/40 py-0.5"
                      >
                        <span
                          className="truncate text-[10px] text-clinical-faint"
                          title={k}
                        >
                          {k}
                        </span>
                        <span className="tnum text-[11px] font-semibold">
                          {fmt((f as unknown as Record<string, number>)[k])}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Waiting>
              Nothing to compute yet - an average or a trend needs a full 30 s
              of readings behind it. The first set of 22 numbers appears the
              moment the window above fills.
            </Waiting>
          )}
          <Note>
            This exact list, in this exact order, is the contract. The same code
            computes it during training and during live use - so the model sees
            the identical shape of input in both, which is what stops a whole
            category of silent bugs.
          </Note>
        </Stage>

        <Flow label="the same 22 numbers go to every model" active={!!f} />

        {/* 4 - the four models */}
        <Stage
          index={4}
          title="Four different models each form an opinion"
          subtitle="Same input, four genuinely different ways of reasoning about it."
          active={!!base}
          wide
        >
          {base ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {BASE_MODEL_ORDER.filter((k) => k in base).map((key) => {
                  const v = base[key];
                  return (
                    <div
                      key={key}
                      className="border-2 border-clinical-border bg-clinical-surface-2 p-3"
                    >
                      <div className="mb-1 flex items-baseline justify-between">
                        <h3 className="text-sm font-bold">
                          {BASE_MODEL_LABELS[key] ?? key}
                        </h3>
                        <span
                          className="tnum text-sm font-bold"
                          style={{ color: stressColor(v) }}
                        >
                          {v.toFixed(2)}
                        </span>
                      </div>
                      <div className="my-2 bg-clinical-surface p-1">
                        {key === "svm" && <SvmVisual p={v} />}
                        {key === "random_forest" && <ForestVisual p={v} />}
                        {key === "xgboost" && <BoostingVisual p={v} />}
                        {key === "mlp" && <MlpVisual p={v} />}
                      </div>
                      <p className="text-[10px] leading-snug text-clinical-muted">
                        {MODEL_BLURB[key]}
                      </p>
                    </div>
                  );
                })}
              </div>

              <div className="mt-4 border-2 border-clinical-border bg-clinical-surface-2 px-4 py-3">
                <div className="flex items-baseline justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider">
                    How much they disagree right now
                  </span>
                  <span className="tnum text-sm font-bold">
                    {spread.toFixed(2)}
                  </span>
                </div>
                <div className="mt-2 h-2 border-2 border-clinical-border bg-clinical-surface">
                  <div
                    className="h-full bg-clinical-accent transition-[width] duration-500"
                    style={{ width: `${clamp01(spread / 0.7) * 100}%` }}
                  />
                </div>
                <p className="mt-2 text-[11px] leading-snug text-clinical-muted">
                  {spread > 0.4
                    ? "Wide disagreement - this is a genuinely ambiguous window, and exactly where combining models can help."
                    : "The four broadly agree here, so any way of combining them lands in much the same place."}
                </p>
              </div>
            </>
          ) : (
            <Waiting>
              The models are idle until they receive a complete feature vector.
              They never see raw sensor readings - only the 22 numbers above.
            </Waiting>
          )}
          <Note>
            <strong>The pictures are illustrations of the method, not the
            actual weights.</strong> Every number shown is real - produced by the
            deployed models - but a readable drawing of 300 real trees or 64 real
            neurons isn’t possible at this size, so the geometry is stylised to
            show <em>how each model thinks</em>.
          </Note>
        </Stage>

        <Flow label="four probabilities" active={!!base} />

        {/* 5 - ensemble */}
        <Stage
          index={5}
          title="A referee model weighs the four opinions"
          subtitle="Stacking: a small model that learned, from data, how much to trust each one."
          active={!!p}
        >
          {base && p ? (
            <div className="grid gap-5 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
              <div className="space-y-2">
                {BASE_MODEL_ORDER.filter((k) => k in base).map((k) => (
                  <ProbBar
                    key={k}
                    label={BASE_MODEL_LABELS[k] ?? k}
                    value={base[k]}
                  />
                ))}
              </div>

              <div className="hidden sm:block" aria-hidden>
                <svg width="60" height="120">
                  {[0, 1, 2, 3].map((i) => (
                    <line
                      key={i}
                      x1="0"
                      y1={18 + i * 28}
                      x2="46"
                      y2="60"
                      stroke="var(--clinical-accent)"
                      strokeWidth="1.6"
                      opacity="0.5"
                    />
                  ))}
                  <circle cx="52" cy="60" r="7" fill="var(--clinical-accent)" />
                </svg>
              </div>

              <div>
                <p className="mb-1.5 text-xs font-bold uppercase tracking-wider text-clinical-muted">
                  Combined
                </p>
                <div
                  className="tnum text-4xl font-bold leading-none"
                  style={{ color: stressColor(pStress) }}
                >
                  {pStress.toFixed(3)}
                </div>
                <p className="mt-1 text-xs text-clinical-muted">
                  P(stress) for this window
                </p>
                <p className="mt-3 text-[11px] leading-snug text-clinical-muted">
                  The referee leans hardest on the SVM - it learned that from
                  held-out data, nobody set it by hand.
                </p>
              </div>
            </div>
          ) : (
            <Waiting>
              With no base-model opinions yet, there is nothing to referee.
            </Waiting>
          )}
        </Stage>

        <Flow label="one probability, every 5 s" active={!!p} />

        {/* 6 - smoothing */}
        <Stage
          index={6}
          title="Smooth it, so the display doesn’t flicker"
          subtitle="Each new answer is blended with the recent past instead of replacing it."
          active={!!p}
        >
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <p className="mb-1 text-xs text-clinical-muted">
                Raw, window by window
              </p>
              <Spark
                values={c.predictionsSoFar.map((x) => x.raw_proba.stress)}
                width={300}
                height={54}
                color="var(--clinical-faint)"
              />
            </div>
            <div>
              <p className="mb-1 text-xs text-clinical-muted">After smoothing</p>
              <Spark
                values={c.predictionsSoFar.map((x) =>
                  x.smoothed_label === "stress"
                    ? x.smoothed_confidence
                    : 1 - x.smoothed_confidence,
                )}
                width={300}
                height={54}
                color="var(--clinical-accent)"
              />
            </div>
          </div>
          <Note>
            Raw predictions can jump between neighbouring windows. Smoothing
            trades a little responsiveness for a reading that a person can
            actually watch without it strobing.
          </Note>
        </Stage>

        <Flow label="smoothed reading" active={!!p} />

        {/* 7 - decision */}
        <Stage
          index={7}
          title="Show a state - and only nag if it persists"
          subtitle="Above 0.5 reads as stress. The breathing prompt needs it sustained, not a single spike."
          active={!!p}
        >
          {p ? (
            <div className="flex flex-wrap items-center gap-6">
              <div
                className="grid h-28 w-28 shrink-0 place-items-center border-4 transition-colors duration-500"
                style={{
                  borderColor: stressColor(smoothedStress),
                  background: "var(--clinical-surface-2)",
                }}
              >
                <div className="text-center">
                  <div
                    className="tnum text-2xl font-bold leading-none"
                    style={{ color: stressColor(smoothedStress) }}
                  >
                    {Math.round(smoothedStress * 100)}%
                  </div>
                  <div className="mt-1 text-[10px] font-bold uppercase tracking-wider">
                    {p.smoothed_label}
                  </div>
                </div>
              </div>
              <div className="min-w-[200px] flex-1 space-y-2">
                <ProbBar
                  label="Smoothed P(stress)"
                  value={smoothedStress}
                  emphasis
                  sublabel="The centre line is the 0.5 decision threshold."
                />
                <p className="text-[11px] leading-snug text-clinical-muted">
                  {smoothedStress >= 0.7
                    ? "Sustained above the alert threshold - this is where the app would offer a breathing exercise."
                    : "Below the alert threshold. The app stays quiet."}
                </p>
              </div>
            </div>
          ) : (
            <Waiting>
              No reading to display until the first prediction lands.
            </Waiting>
          )}
          <Note>
            This is a research prototype, not a medical device. “Stress” means
            “this looks like the labelled stress examples it was trained on” -
            nothing more.
          </Note>
        </Stage>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- helpers -- */

/** Placeholder that explains *why* a stage is empty, rather than just
 *  saying "waiting" - the warm-up is part of the story, not dead air. */
function Waiting({ children }: { children: React.ReactNode }) {
  return (
    <p className="mx-auto max-w-md py-6 text-center text-xs leading-relaxed text-clinical-faint">
      {children}
    </p>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center px-6 text-center">
      <div>{children}</div>
    </div>
  );
}

function fmt(v: number | undefined): string {
  if (v === undefined || !Number.isFinite(v)) return "-";
  const a = Math.abs(v);
  if (a >= 1000) return v.toFixed(0);
  if (a >= 10) return v.toFixed(1);
  if (a >= 1) return v.toFixed(2);
  return v.toFixed(3);
}

function SensorTile({
  label,
  unit,
  value,
  series,
}: {
  label: string;
  unit: string;
  value: number | null;
  series: number[];
}) {
  return (
    <div className="border-2 border-clinical-border bg-clinical-surface-2 p-2.5">
      <p className="text-[10px] font-bold uppercase tracking-wider text-clinical-faint">
        {label}
      </p>
      <p className="tnum text-xl font-bold leading-tight">
        {value === null || !Number.isFinite(value) ? "-" : fmt(value)}
        <span className="ml-1 text-[10px] font-normal text-clinical-faint">
          {unit}
        </span>
      </p>
      <div className="mt-1">
        <Spark values={series} width={150} height={28} />
      </div>
    </div>
  );
}

function WindowBar({
  warmup,
  nextIn,
  full,
}: {
  warmup: number;
  nextIn: number;
  full: boolean;
}) {
  return (
    <div>
      <div className="relative h-12 border-2 border-clinical-border bg-clinical-surface-2">
        {/* the filling 30 s window */}
        <div
          className="absolute inset-y-0 left-0 bg-clinical-accent-soft transition-[width] duration-200"
          style={{ width: `${clamp01(warmup) * 100}%` }}
        />
        {/* 5 s stride ticks */}
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="absolute inset-y-0 w-px bg-clinical-border/50"
            style={{ left: `${(i / 6) * 100}%` }}
          />
        ))}
        <div className="absolute inset-0 grid place-items-center">
          <span className="tnum text-xs font-bold">
            {full ? "30 s window full" : `filling… ${Math.round(warmup * 30)} / 30 s`}
          </span>
        </div>
      </div>
      <p className="tnum mt-2 text-center text-[11px] text-clinical-muted">
        next prediction in{" "}
        <span className="font-bold text-clinical-text">
          {nextIn.toFixed(1)} s
        </span>
      </p>
    </div>
  );
}

function Header({ clock }: { clock: ReturnType<typeof usePipelineClock> }) {
  return (
    <header className="sticky top-0 z-20 mb-6 border-b-2 border-clinical-border bg-clinical-surface/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-5 gap-y-2 px-5 py-3">
        <div className="mr-auto">
          <h1 className="text-lg font-bold leading-tight">
            How a stress reading is made
          </h1>
          <p className="text-xs text-clinical-muted">
            Sensors → features → four models → one answer. Running on the real
            pipeline.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => clock.setPlaying(!clock.playing)}
            className="grid h-9 w-9 place-items-center border-2 border-clinical-border bg-clinical-surface transition-transform hover:-translate-y-[2px]"
            aria-label={clock.playing ? "Pause" : "Play"}
          >
            {clock.playing ? (
              <Pause className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </button>
          <button
            onClick={clock.restart}
            className="grid h-9 w-9 place-items-center border-2 border-clinical-border bg-clinical-surface transition-transform hover:-translate-y-[2px]"
            aria-label="Restart"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
          {[1, 2, 4].map((sp) => (
            <button
              key={sp}
              onClick={() => clock.setSpeed(sp)}
              className={[
                "tnum h-9 border-2 px-2.5 text-xs font-bold transition-transform hover:-translate-y-[2px]",
                clock.speed === sp
                  ? "border-clinical-accent bg-clinical-accent text-white"
                  : "border-clinical-border bg-clinical-surface",
              ].join(" ")}
            >
              {sp}×
            </button>
          ))}
        </div>

        <div className="w-full">
          <input
            type="range"
            min={0}
            max={clock.durationS || 180}
            step={0.5}
            value={clock.t}
            onChange={(e) => clock.seek(Number(e.target.value))}
            className="w-full accent-[var(--clinical-accent)]"
            aria-label="Scrub the session"
          />
          <div className="tnum flex justify-between text-[10px] text-clinical-faint">
            <span>{clock.t.toFixed(0)}s</span>
            <span>{clock.durationS}s</span>
          </div>
        </div>
      </div>
    </header>
  );
}
