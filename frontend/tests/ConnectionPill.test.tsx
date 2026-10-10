import { act } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConnectionPill } from "@/components/live/ConnectionPill";
import { useLiveStore } from "@/stores/liveStore";

describe("ConnectionPill", () => {
  it("reflects the live store connection status", () => {
    act(() => useLiveStore.getState().setStatus("open"));
    render(<ConnectionPill />);
    expect(screen.getByText("Connected")).toBeInTheDocument();

    act(() => useLiveStore.getState().setStatus("closed"));
    expect(screen.getByText("Disconnected")).toBeInTheDocument();

    act(() => useLiveStore.getState().setStatus("demo"));
    expect(screen.getByText("Demo mode")).toBeInTheDocument();
  });
});
