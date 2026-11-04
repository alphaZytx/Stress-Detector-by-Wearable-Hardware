import { NavLink } from "react-router-dom";
import {
  Activity,
  Radio,
  HeartPulse,
  History,
  LogOut,
  Moon,
  PanelLeftClose,
  Route,
  Settings,
  Sun,
  Target,
  Wind,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { useAuth } from "@/hooks/useAuth";
import { useSettingsStore } from "@/stores/settingsStore";

const NAV = [
  { to: "/live", label: "Live", Icon: Activity },
  { to: "/sensors", label: "Sensors", Icon: Radio },
  { to: "/history", label: "History", Icon: History },
  { to: "/calibration", label: "Calibration", Icon: Target },
  { to: "/breathing", label: "Breathing", Icon: Wind },
  // Public route, but linked here too so it's discoverable from inside the app.
  { to: "/explain", label: "How it works", Icon: Route },
  { to: "/settings", label: "Settings", Icon: Settings },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, logout } = useAuth();
  const theme = useSettingsStore((s) => s.theme);
  const toggleTheme = useSettingsStore((s) => s.toggleTheme);

  return (
    <aside
      className={cn(
        "h-full w-64 shrink-0 flex-col border-r-2 border-clinical-border bg-clinical-surface",
        open ? "fixed inset-y-0 left-0 z-30 flex lg:static" : "hidden",
      )}
    >
      {/* Brand + collapse */}
      <div className="flex items-center gap-3 border-b-2 border-clinical-border px-4 py-4">
        <span
          className="grid h-10 w-10 shrink-0 place-items-center rounded-none border-2 border-clinical-border bg-clinical-accent text-white shadow-sm"
        >
          <HeartPulse className="h-5 w-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-display text-sm font-bold uppercase tracking-wide text-clinical-text">
            Stress Monitor
          </div>
          <div className="truncate font-mono text-[11px] uppercase tracking-wide text-clinical-faint">
            HRV dashboard
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Collapse menu"
          aria-expanded={open}
          title="Collapse menu"
          className="grid h-8 w-8 shrink-0 place-items-center rounded-none border-2 border-transparent text-clinical-muted transition-colors hover:border-clinical-border hover:text-clinical-text cursor-pointer"
        >
          <PanelLeftClose className="h-5 w-5" aria-hidden />
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-2 p-3">
        {NAV.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "group flex items-center gap-3 rounded-none border-2 px-3 py-2.5 text-sm font-semibold uppercase tracking-wide transition-all duration-100 cursor-pointer",
                isActive
                  ? "border-clinical-border bg-clinical-accent text-white shadow-sm"
                  : "border-transparent text-clinical-muted hover:border-clinical-border hover:text-clinical-text",
              )
            }
          >
            <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t-2 border-clinical-border p-3">
        <button
          onClick={toggleTheme}
          title={theme === "light" ? "Dark mode" : "Light mode"}
          className="mb-2 flex w-full items-center gap-3 rounded-none border-2 border-transparent px-3 py-2.5 text-sm font-semibold uppercase tracking-wide text-clinical-muted transition-colors duration-100 hover:border-clinical-border hover:text-clinical-text cursor-pointer"
        >
          {theme === "light" ? (
            <Moon className="h-[18px] w-[18px] shrink-0" aria-hidden />
          ) : (
            <Sun className="h-[18px] w-[18px] shrink-0" aria-hidden />
          )}
          <span>{theme === "light" ? "Dark mode" : "Light mode"}</span>
        </button>

        <div className="flex items-center justify-between gap-2 border-2 border-clinical-border bg-clinical-surface-2 px-3 py-2">
          <div className="min-w-0">
            <div className="truncate text-sm font-bold text-clinical-text">
              {user?.display_name || user?.email || "User"}
            </div>
            <div className="truncate font-mono text-[11px] text-clinical-faint">{user?.email}</div>
          </div>
          <button
            onClick={logout}
            aria-label="Log out"
            title="Log out"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-none border-2 border-transparent text-clinical-muted transition-colors duration-100 hover:border-clinical-danger hover:text-clinical-danger cursor-pointer"
          >
            <LogOut className="h-[18px] w-[18px]" aria-hidden />
          </button>
        </div>
      </div>
    </aside>
  );
}
