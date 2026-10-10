import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { HeartPulse } from "lucide-react";
import { ApiError } from "@/api/client";
import { Button } from "@/components/primitives/Button";
import { Input } from "@/components/primitives/Input";
import { AuroraBackground } from "@/components/decorative/AuroraBackground";
import { useAuth } from "@/hooks/useAuth";

interface LocationState {
  from?: { pathname: string };
}

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = (location.state as LocationState)?.from?.pathname ?? "/live";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate(returnTo, { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Login failed. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthScaffold
      title="Welcome back"
      subtitle="Sign in to your stress-monitoring dashboard."
    >
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p role="alert" className="text-sm text-clinical-danger">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" loading={loading} className="mt-1">
          Sign in
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-clinical-muted">
        No account?{" "}
        <Link to="/register" className="font-medium text-clinical-accent hover:underline">
          Create one
        </Link>
      </p>
    </AuthScaffold>
  );
}

export function AuthScaffold({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden px-4 py-10">
      <AuroraBackground />

      <div className="relative z-10 w-full max-w-md animate-fade-in">
        {/* Brand lockup */}
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-5 grid h-16 w-16 place-items-center rounded-none border-2 border-clinical-border bg-clinical-accent text-white shadow-card">
            <HeartPulse className="h-8 w-8" aria-hidden />
          </span>
          <div className="font-display text-sm font-bold uppercase tracking-[0.2em] text-clinical-accent">
            Stress Monitor
          </div>
          <h1 className="mt-4 font-display text-3xl font-bold tracking-tight text-clinical-text">
            {title}
          </h1>
          <p className="mt-2 max-w-xs text-sm text-clinical-muted">{subtitle}</p>
        </div>

        {/* Glass auth card floating on the aurora. */}
        <div className="surface-raised rounded-none p-7">{children}</div>

        {/* decorative pulse-style biosignal line below the card */}
        <svg viewBox="0 0 600 60" className="mx-auto mt-8 h-9 w-full max-w-sm opacity-50" fill="none" aria-hidden>
          <path
            d="M0 30 H120 l14 -20 14 40 16 -30 14 10 H300 l14 -22 16 34 14 -16 H600"
            stroke="var(--clinical-accent)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}
