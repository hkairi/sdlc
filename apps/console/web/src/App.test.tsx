// @vitest-environment jsdom
// @vitest-environment-options {"url": "http://127.0.0.2:8765/"}
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { SuiviStatus } from "./lib/suivi";

const project = { id: 1, name: "Atlas", slug: "atlas" };

const notReady: SuiviStatus = {
  ready: false,
  generated_at: null,
  html_path: "docs/suivi-atlas.html",
  json_path: "docs/suivi/atlas.json",
  stale: false,
  summary: {
    features: 1,
    tasks: 3,
    done: 1,
    doing: 1,
    todo: 1,
    blocked: 0,
    cancelled: 0,
    progress_percent: 33,
  },
  open_on_ready: true,
  url: "/api/projects/1/suivi?format=html",
};

const ready: SuiviStatus = {
  ...notReady,
  ready: true,
  generated_at: "2026-10-20T10:00:00+00:00",
};

const overview = {
  generated_at: "2026-10-20T10:00:00+00:00",
  project,
  summary: { features: 1, tasks: 3, done: 1, doing: 1, todo: 1, blocked: 0 },
  kpis: [],
  pending_decisions: [],
  pending_decisions_source: "state.json",
  pipeline: [],
  risks: [],
  risks_source: "state.json",
};

const features = {
  project,
  filters: { phase: null, gate: null },
  available_phases: [],
  available_gates: [],
  features: [],
  total: 0,
  inconsistencies: [],
  sources: {},
};

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

class MemoryStorage {
  private readonly values = new Map<string, string>();

  get length(): number {
    return this.values.size;
  }

  clear(): void {
    this.values.clear();
  }

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  key(index: number): string | null {
    return Array.from(this.values.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

function mockApi(options: { initiallyReady?: boolean } = {}) {
  let statusCalls = 0;
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const url = String(input);
    if (url === "/api/projects") {
      return Promise.resolve(jsonResponse([project]));
    }
    if (url === "/api/projects/1/suivi/status") {
      statusCalls += 1;
      const payload = options.initiallyReady || statusCalls > 1 ? ready : notReady;
      return Promise.resolve(jsonResponse(payload));
    }
    if (url === "/api/projects/1/overview") {
      return Promise.resolve(jsonResponse(overview));
    }
    if (url.startsWith("/api/projects/1/features")) {
      return Promise.resolve(jsonResponse(features));
    }
    if (url === "/api/projects/1/suivi?format=json") {
      return Promise.resolve(jsonResponse({}));
    }
    return Promise.reject(new Error(`URL inattendue : ${url}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("App suivi", () => {
  beforeEach(() => {
    const storage = new MemoryStorage();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: storage,
    });
    window.localStorage.clear();
    vi.spyOn(window, "open").mockReturnValue({} as Window);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("ouvre le suivi une seule fois quand la génération est prête", async () => {
    mockApi();
    render(<App />);

    const generate = await screen.findByRole("button", { name: /Générer le suivi/ });
    fireEvent.click(generate);

    await waitFor(() => {
      expect(window.open).toHaveBeenCalledTimes(1);
    });
    expect(window.open).toHaveBeenCalledWith(
      "/api/projects/1/suivi?format=html",
      "_blank",
      "noopener,noreferrer",
    );
    expect(
      screen.getByRole("link", { name: "Ouvrir le suivi" }).getAttribute("href"),
    ).toBe("/api/projects/1/suivi?format=html");
    expect(screen.getByRole("status").textContent).toContain("Le suivi s'est ouvert");
    expect(
      screen.getByText((_content, element) =>
        element?.tagName === "P" && (element.textContent ?? "").includes("Dernière génération"),
      ),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Générer le suivi/ }));
    await waitFor(() => {
      const button = screen.getByRole("button", { name: /Générer le suivi/ }) as HTMLButtonElement;
      expect(button.disabled).toBe(false);
    });
    expect(window.open).toHaveBeenCalledTimes(1);
  });

  it("expose le lien persistant et les libellés accessibles quand l'ouverture est désactivée", async () => {
    const disabled = { ...ready, open_on_ready: false };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url === "/api/projects") {
          return Promise.resolve(jsonResponse([project]));
        }
        if (url === "/api/projects/1/suivi/status") {
          return Promise.resolve(jsonResponse(disabled));
        }
        if (url === "/api/projects/1/overview") {
          return Promise.resolve(jsonResponse(overview));
        }
        if (url.startsWith("/api/projects/1/features")) {
          return Promise.resolve(jsonResponse(features));
        }
        return Promise.reject(new Error(`URL inattendue : ${url}`));
      }),
    );

    render(<App />);

    expect(await screen.findByLabelText("Projet")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Générer le suivi/ })).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Ouvrir le suivi" }).getAttribute("href"),
    ).toBe("/api/projects/1/suivi?format=html");
    expect(screen.getByRole("status")).toBeTruthy();
    expect(
      await screen.findByText(/L'ouverture automatique est désactivée/),
    ).toBeTruthy();
    expect(window.open).not.toHaveBeenCalled();
  });
});
