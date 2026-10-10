import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { Button } from "@/components/primitives/Button";
import { Input } from "@/components/primitives/Input";
import { useAuth } from "@/hooks/useAuth";
import { AuthScaffold } from "./Login";

export function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    setLoading(true);
    try {
      await register(email, password, displayName || undefined);
      navigate("/live", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Registration failed. Try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthScaffold
      title="Create your account"
      subtitle="Set up a personal stress-monitoring profile."
    >
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <Input
          label="Display name (optional)"
          autoComplete="name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
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
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={
            password && password.length < 6 ? "At least 6 characters" : undefined
          }
        />
        {error && (
          <p role="alert" className="text-sm text-clinical-danger">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" loading={loading} className="mt-1">
          Create account
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-clinical-muted">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-clinical-accent hover:underline">
          Sign in
        </Link>
      </p>
    </AuthScaffold>
  );
}
