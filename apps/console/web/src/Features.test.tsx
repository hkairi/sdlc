// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Features from "./Features";

const inconsistency = {
  id: 1,
  feature_key: "F-1",
  task_key: "1.1",
  kind: "etat_done_case_vide",
  message: "state.json indique done mais tasks.md n'est pas coché",
  state_status: "done",
  tasks_md_checked: false,
  created_at: "2026-10-20T10:00:00+00:00",
};

const featuresResponse = {
  project: { id: 1, name: "Atlas", slug: "atlas" },
  filters: { phase: "impl", gate: null },
  available_phases: [
    { id: "impl", name: "Implémentation" },
    { id: "validation", name: "Validation" },
  ],
  available_gates: [
    { id: "non_mesure", name: "Non mesuré", source: "reports/gates" },
  ],
  features: [
    {
      id: 1,
      key: "F-1",
      name: "Console",
      status: "doing",
      status_label: "En cours",
      phase: {
        id: "impl",
        name: "Implémentation",
        status: "doing",
        source: "state.json + tasks",
      },
      phase_id: "impl",
      phase_name: "Implémentation",
      phase_status: "doing",
      objective: "Construire la console",
      change: "console-sdlc",
      spec_path: "openspec/changes/console-sdlc/design.md",
      tasks_file: "openspec/changes/console-sdlc/tasks.md",
      sources: {
        proposal: "openspec/changes/console-sdlc/proposal.md",
        design: "openspec/changes/console-sdlc/design.md",
      },
      version: "0.1",
      delivered: false,
      blocked: false,
      repositories: [{ id: 1, name: "api" }],
      tasks: [
        {
          id: 11,
          key: "1.1",
          title: "Implémenter",
          status: "done",
          status_label: "Terminé",
          lot: "L1",
          executor: "Alice",
          reviewer: "Bob",
          updated_at: "2026-10-20T10:00:00+00:00",
          report_url: "/api/projects/1/tasks/11/report",
        },
      ],
      task_summary: {
        total: 1,
        done: 1,
        doing: 0,
        todo: 0,
        blocked: 0,
        progress_percent: 100,
      },
      coverage: {
        status: "not_measured",
        value: null,
        label: "non mesuré",
        source: "reports/coverage",
        detail: "aucune preuve de couverture ingérée",
      },
      gate: {
        status: "not_measured",
        value: null,
        label: "non mesuré",
        source: "reports/gates",
        detail: "aucun gate ingéré",
      },
      executors: ["Alice"],
      reviewers: ["Bob"],
      updated_at: "2026-10-20T10:00:00+00:00",
      inconsistencies: [inconsistency],
    },
  ],
  total: 1,
  inconsistencies: [inconsistency],
  sources: {
    phase: "state.json",
    coverage: "reports/coverage",
    gate: "reports/gates",
    inconsistencies: "tasks.md + state.json",
  },
};

const taskDetail = {
  id: 11,
  key: "1.1",
  title: "Implémenter",
  description: "Implémenter la vue",
  status: "done",
  status_label: "Terminé",
  lot: "L1",
  files: ["apps/console/src/Features.tsx"],
  acceptance: "Le détail s'ouvre",
  note: "Rapport de fin de tâche",
  executor: "Alice",
  reviewer: "Bob",
  updated_at: "2026-10-20T10:00:00+00:00",
  feature: {
    id: 1,
    key: "F-1",
    name: "Console",
    phase: {
      id: "impl",
      name: "Implémentation",
      status: "doing",
      source: "state.json + tasks",
    },
  },
  repositories: [{ id: 1, name: "api" }],
  report_url: "/api/projects/1/tasks/11/report",
  report_available: true,
  source: "state.json",
};

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  window.history.replaceState({}, "", "/?phase=impl");
  fetchMock = vi.fn((input: string | URL | Request) => {
    const url = String(input);
    if (url === "/api/projects/1/tasks/11") {
      return Promise.resolve(jsonResponse(taskDetail));
    }
    if (url.startsWith("/api/projects/1/features")) {
      return Promise.resolve(jsonResponse(featuresResponse));
    }
    return Promise.reject(new Error(`URL inattendue : ${url}`));
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});

describe("Features", () => {
  it("affiche les features, les incohérences et les filtres depuis l'URL", async () => {
    render(<Features projectId={1} />);

    expect(await screen.findByRole("heading", { name: "Console" })).toBeTruthy();
    expect(
      screen.getByText("1 incohérence(s) tasks.md ↔ state.json"),
    ).toBeTruthy();
    expect(screen.getByText(/Couverture : non mesuré/)).toBeTruthy();
    expect(screen.getByText(/Spec : openspec\/changes\/console-sdlc\/design\.md/)).toBeTruthy();
    expect(screen.getByText(/Exécutants : Alice/)).toBeTruthy();
    expect(screen.getByText(/1 \/ 1 tâches terminées/)).toBeTruthy();
    expect(
      (screen.getByLabelText("Phase") as HTMLSelectElement).value,
    ).toBe("impl");
    const firstCall = String(fetchMock.mock.calls[0]?.[0]);
    expect(firstCall).toContain("/api/projects/1/features?phase=impl");
  });

  it("ouvre le détail d'une tâche avec fichiers, critères et rapport", async () => {
    render(<Features projectId={1} />);

    const taskButton = await screen.findByRole("button", {
      name: /1\.1 Implémenter/,
    });
    fireEvent.click(taskButton);

    expect(await screen.findByRole("heading", { name: "1.1 Implémenter" })).toBeTruthy();
    expect(screen.getByText(/apps\/console\/src\/Features\.tsx/)).toBeTruthy();
    expect(screen.getByText(/Le détail s'ouvre/)).toBeTruthy();
    expect(screen.getByText(/Rapport de fin de tâche/)).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "Ouvrir le rapport de fin de tâche" })
        .getAttribute("href"),
    ).toBe("/api/projects/1/tasks/11/report");
  });

  it("conserve les filtres phase et gate dans l'URL", async () => {
    render(<Features projectId={1} />);
    await screen.findByRole("heading", { name: "Console" });

    fireEvent.change(screen.getByLabelText("Gate"), {
      target: { value: "non_mesure" },
    });

    await waitFor(() => {
      expect(window.location.search).toContain("phase=impl");
      expect(window.location.search).toContain("gate=non_mesure");
    });
    const lastCall = String(fetchMock.mock.calls.at(-1)?.[0]);
    expect(lastCall).toContain("phase=impl");
    expect(lastCall).toContain("gate=non_mesure");
  });
});
