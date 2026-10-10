import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Menu } from "lucide-react";
import { useLiveStream } from "@/hooks/useLiveStream";
import { Sidebar } from "./Sidebar";

/**
 * App shell for authenticated routes. Mounts useLiveStream ONCE here so the
 * liveStore is fed regardless of which route is active.
 *
 * The sidebar is a hamburger-collapsible drawer: on lg it sits in flow and
 * pushes content; on small screens it overlays with a backdrop. When closed, a
 * floating hamburger (top-left) reopens it on every route.
 */
export function AppShell() {
  useLiveStream();
  const [open, setOpen] = useState(true);

  return (
    <div className="relative flex h-screen overflow-hidden">
      {/* mobile backdrop */}
      {open && (
        <button
          aria-label="Close menu"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
        />
      )}

      <Sidebar open={open} onClose={() => setOpen(false)} />

      {/* floating reopen hamburger, visible whenever the drawer is closed */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          aria-label="Open menu"
          aria-expanded={false}
          className="fixed left-4 top-4 z-40 grid h-11 w-11 place-items-center rounded-none border-2 border-clinical-border bg-clinical-surface text-clinical-text shadow-card transition-transform hover:-translate-x-[2px] hover:-translate-y-[2px] active:translate-x-0 active:translate-y-0 cursor-pointer"
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>
      )}

      <main className="relative z-10 flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
