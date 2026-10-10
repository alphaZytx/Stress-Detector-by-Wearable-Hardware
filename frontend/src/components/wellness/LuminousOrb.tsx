import { CSSProperties } from "react";

/**
 * Luminous light-trail orb - overlapping conic-gradient rings, each masked to a
 * thin arc, blurred, 3D-tilted, and rotating at its OWN speed + direction so they
 * smear into light streaks and overlap like a coil (long-exposure light-painting
 * look). Additive blending (screen) over a dark spotlight void makes the neon
 * trails pop. Rotation is paused by prefers-reduced-motion.
 */

interface RingSpec {
  inset: string;
  thickness: number; // px arc width
  duration: number; // s per rotation
  reverse?: boolean;
  blur: number;
  tiltX: number; // deg - coil overlap
  tiltZ: number; // deg - offset
  gradient: string; // conic streak
  opacity?: number;
}

const RINGS: RingSpec[] = [
  {
    inset: "0%", thickness: 4, duration: 7, blur: 2, tiltX: 16, tiltZ: 8, opacity: 1,
    gradient: "conic-gradient(from 10deg, transparent 0deg, #67e8f9 60deg, #ffffff 100deg, #a5f3fc 130deg, transparent 230deg)",
  },
  {
    inset: "3%", thickness: 7, duration: 11, reverse: true, blur: 3.5, tiltX: -22, tiltZ: -10, opacity: 0.85,
    gradient: "conic-gradient(from 200deg, transparent 0deg, #818cf8 55deg, #6366f1 110deg, transparent 215deg)",
  },
  {
    inset: "1%", thickness: 2.5, duration: 9, blur: 1, tiltX: 26, tiltZ: -6, opacity: 1,
    gradient: "conic-gradient(from 120deg, transparent 0deg, #ffffff 45deg, #67e8f9 85deg, transparent 165deg)",
  },
  {
    inset: "6%", thickness: 8, duration: 16, blur: 4.5, tiltX: -12, tiltZ: 16, opacity: 0.7,
    gradient: "conic-gradient(from 300deg, transparent 0deg, #2dd4bf 55deg, #34d399 110deg, transparent 205deg)",
  },
  {
    inset: "2%", thickness: 4, duration: 8, reverse: true, blur: 2.5, tiltX: 8, tiltZ: -18, opacity: 0.6,
    gradient: "conic-gradient(from 60deg, transparent 0deg, #fb7185 45deg, #fbbf24 85deg, transparent 165deg)",
  },
];

function spinnerStyle(r: RingSpec): CSSProperties {
  const mask = `radial-gradient(farthest-side, transparent calc(100% - ${r.thickness}px), #000 calc(100% - ${r.thickness}px))`;
  return {
    position: "absolute",
    inset: 0,
    borderRadius: "9999px",
    background: r.gradient,
    opacity: r.opacity ?? 1,
    filter: `blur(${r.blur}px)`,
    mixBlendMode: "screen",
    WebkitMaskImage: mask,
    maskImage: mask,
    animation: `${r.reverse ? "ring-rotate-rev" : "ring-rotate"} ${r.duration}s linear infinite`,
    willChange: "transform",
  };
}

export function LuminousOrb({ children }: { children?: React.ReactNode }) {
  return (
    <div className="absolute inset-0 grid place-items-center [perspective:700px]" aria-hidden>
      {/* Dark spotlight void so the neon streaks read against darkness. */}
      <div
        className="absolute inset-[-22%] rounded-full"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(2,10,20,0.92) 0%, rgba(3,16,28,0.7) 42%, transparent 72%)",
        }}
      />
      {/* Hollow core. */}
      <div
        className="absolute inset-[20%] rounded-full"
        style={{ background: "radial-gradient(circle at 50% 42%, rgba(8,22,34,0.6), rgba(2,8,16,0.95) 75%)" }}
      />

      {RINGS.map((r, i) => (
        <div
          key={i}
          className="absolute"
          style={{
            inset: r.inset,
            transform: `rotateX(${r.tiltX}deg) rotateZ(${r.tiltZ}deg)`,
            transformStyle: "preserve-3d",
          }}
        >
          <div style={spinnerStyle(r)} />
        </div>
      ))}

      {children && (
        <div className="absolute inset-0 grid place-items-center">{children}</div>
      )}
    </div>
  );
}
