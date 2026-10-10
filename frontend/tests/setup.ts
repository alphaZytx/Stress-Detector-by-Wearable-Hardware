import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Recharts' ResponsiveContainer uses ResizeObserver, absent in jsdom.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (ResizeObserverStub as never);

afterEach(() => {
  cleanup();
  // Go through `window` deliberately: Node >= 26 exposes its own built-in
  // `localStorage` global which is `undefined` unless the process was started
  // with --localstorage-file, and it shadows the jsdom one in the bare scope.
  // Resolving off `window` always finds jsdom's implementation.
  window.localStorage?.clear();
});
