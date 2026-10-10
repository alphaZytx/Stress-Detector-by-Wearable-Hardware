/**
 * Lightweight inline sparkline, shared by the model-input and raw-stream views.
 *
 * Deliberately hand-rolled SVG rather than Recharts: these render 20+ at a time
 * and update every second, where a ResponsiveContainer each would dominate the
 * frame budget.
 */
export function MiniSpark({
  values,
  color,
  className = "h-6 w-full",
}: {
  values: number[];
  color: string;
  className?: string;
}) {
  if (values.length < 2) {
    return <div className={className} aria-hidden />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = 100 / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(2)},${(22 - ((v - min) / span) * 20).toFixed(2)}`)
    .join(" ");

  return (
    <svg
      viewBox="0 0 100 24"
      preserveAspectRatio="none"
      className={`${className} overflow-visible`}
      aria-hidden
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
