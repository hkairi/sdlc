// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Overview from "./Overview";

const data = {
  generated_at: "2026-10-20T10:00:00+00:00",
  project: { id: 1, name: "Atlas", slug: "atlas" },
  summary: { features: 1, tasks: 3, done: 1, doing: 1, todo: 1, blocked: 1 },
  kpis: [
    {
      key: "progress",
      label: "Avancement",
      value: 33,
      unit: "%",
      source: "state.json",
      status: "measured",
      detail: "1 / 3 tâches terminées",
    },
    {
      key: "gates",
      label: "Gates",
      value: null,
      unit: null,
      source: "reports/gates/*.json",
      status: "not_measured",
      detail: "aucun gate ingéré",
    },
  ],
  pending_decisions: [
    {
      id: "task:2",
      kind: "tache_bloquee",
      title: "F-1 · 1.2 Décision",
      blocking: false,
      source: "state.json",
      detail: "à suivre",
    },
    {
      id: "task:1",
      kind: "tache_bloquee",
      title: "F-1 · 1.1 Arbitrage",
      blocking: true,
      source: "state.json",
      detail: "décision humaine",
    },
  ],
  pending_decisions_source: "state.json",
  pipeline: [
    {
      id: "cadrage",
      label: "Cadrage",
      status: "done",
      source: "state.json",
      detail: "6 contrôle(s)",
    },
    {
      id: "impl",
      label: "Implémentation",
      status: "doing",
      source: "state.json + tasks",
      detail: "3 tâche(s)",
    },
  ],
  risks: [
    {
      category: "projet",
      severity: "haute",
      title: "Tâche bloquée 1.2",
      detail: "décision humaine",
      source: "state.json",
    },
  ],
  risks_source: "state.json / deploys.jsonl",
};

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Overview", () => {
  it("affiche les KPI avec leur source et les mesures absentes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(data))),
    );
    render(<Overview projectId={1} />);

    expect(await screen.findByRole("heading", { name: "Vue d'ensemble" })).toBeTruthy();
    expect(screen.getByText("Avancement")).toBeTruthy();
    expect(screen.getByText("33%")).toBeTruthy();
    expect(screen.getAllByText("non mesuré").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Source : state.json").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("1 / 3 tâches terminées")).toBeTruthy();
  });

  it("trie les décisions bloquantes, affiche le pipeline et les risques", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(data))),
    );
    render(<Overview projectId={1} />);

    const blocking = await screen.findByText("F-1 · 1.1 Arbitrage");
    const secondary = screen.getByText("F-1 · 1.2 Décision");
    expect(blocking).toBeTruthy();
    expect(secondary).toBeTruthy();
    expect(screen.getByText("Bloquant")).toBeTruthy();
    expect(screen.getByText("Terminé")).toBeTruthy();
    expect(screen.getByText("En cours")).toBeTruthy();
    expect(screen.getByText("Tâche bloquée 1.2")).toBeTruthy();
    expect(screen.getByText("projet")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Pipeline SDLC" })).toBeTruthy();
  });
});
