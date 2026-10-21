// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RunLog from "./RunLog";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly url: string;
  closed = false;
  private readonly listeners = new Map<string, Set<EventListener>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener): void {
    const current = this.listeners.get(type) ?? new Set<EventListener>();
    current.add(listener);
    this.listeners.set(type, current);
  }

  removeEventListener(type: string, listener: EventListener): void {
    this.listeners.get(type)?.delete(listener);
  }

  close(): void {
    this.closed = true;
  }

  emit(type: string, payload: unknown): void {
    const event = new MessageEvent(type, { data: JSON.stringify(payload) });
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RunLog", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  it("affiche le HTML littéralement sans déplacer le focus", () => {
    const outside = document.createElement("button");
    outside.textContent = "hors journal";
    document.body.append(outside);
    outside.focus();

    const { container } = render(<RunLog runId="run 1" />);
    const source = FakeEventSource.instances[0];
    expect(source.url).toBe("/api/runs/run%201/events");

    act(() => {
      source.emit("run.log", { text: "<script>alert(1)</script>\n" });
    });

    expect(screen.getByText(/alert\(1\)/)).toBeTruthy();
    expect(container.querySelector("script")).toBeNull();
    expect(document.activeElement).toBe(outside);
    outside.remove();
  });

  it("annonce le statut final dans une région polie", () => {
    render(<RunLog runId="run-1" />);
    const source = FakeEventSource.instances[0];

    act(() => {
      source.emit("run.status", { status: "done" });
    });

    expect(screen.getByRole("status").textContent).toContain("done");
    expect(source.closed).toBe(true);
  });
});
