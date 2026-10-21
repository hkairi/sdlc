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

const security = {
  generated_at: "2026-10-21T10:00:00+00:00",
  project,
  status: "not_measured",
  run: {
    id: null,
    verdict: "not_run",
    base_verdict: null,
    blocks: false,
    report_path: null,
    generated_at: null,
  },
  findings: [],
  finding_counts: {},
  sbom: {
    status: "not_measured",
    path: null,
    format: null,
    components: null,
    licenses: [],
    packages: [],
    detail: "aucun SBOM",
  },
  licenses: { values: [], count: 0, status: "not_measured", policy: { allowed: [], denied: [], status: "not_declared" } },
  waivers: [],
  agent_surface: {
    agents: [],
    repositories: [],
    recent_runs: [],
    runs_by_status: {},
    read_only_reviews: 0,
    git_write_refused: 0,
    environment_policy: "",
    surface: "",
  },
  sources: {},
};

const quality = {
  generated_at: "2026-10-21T10:00:00+00:00",
  project,
  performance: {
    status: "not_measured",
    verdict: "not_run",
    blocks: false,
    report_path: null,
    generated_at: null,
    budgets: {},
    cases: [],
    signals: [],
    findings: [],
    controls: [],
  },
  data: {
    status: "not_measured",
    verdict: "not_run",
    blocks: false,
    report_path: null,
    generated_at: null,
    controls: [],
    pii: [],
    migrations: [],
    backup: {
      status: "not_measured",
      verified: null,
      restore_tested: null,
      age_hours: null,
      source: "",
      verdict: null,
      reason: null,
    },
    retention_days: null,
    schema: { status: "not_measured", current: null, head: null, up_to_date: null, source: "alembic" },
  },
  sources: {},
};

const agentsData = {
  project,
  filters: { agent_id: null, role: null, status: null },
  runs: [],
  total: 0,
  limit: 50,
  offset: 0,
  has_more: false,
  independence: {
    status: "not_measured",
    window_days: 30,
    total_reviews: 0,
    independent_reviews: 0,
    degraded_reviews: 0,
    degraded_rate_percent: null,
    threshold_percent: 10,
    decision_required: false,
    unmeasured_reviews: 0,
    detail: "aucune revue",
  },
  independence_alert: null,
};

const notifications = { project, notifications: [], total: 0 };

const documents = {
  generated_at: "2026-10-21T10:00:00+00:00",
  project,
  review_days: 90,
  documents: [],
  summary: { expected: 0, present: 0, missing: 0, stale: 0, generated: 0 },
  sources: {},
};

const configuration = {
  project,
  config_file: { path: "sdlc.config.yaml", exists: false, readable: false },
  validation: { valid: false, errors: [], schema_id: null, schema_title: null },
  effective: {},
  origins: [],
  sources: {},
  notice: "",
};

const gates = { project, gates: [], total: 0, limit: 50, offset: 0, has_more: false, next_offset: null };
const findings = { project, findings: [], total: 0, limit: 50, offset: 0, has_more: false, next_offset: null };
const reviewPackages = { project, packages: [], total: 0 };
const decisions = { project, decisions: [], total: 0 };
const reviewers = {
  project,
  selected: null,
  level: "degraded",
  allowed: false,
  waiver_required: true,
  reason: "aucun relecteur",
  candidates: [],
};
const team = {
  project,
  repositories: [],
  persons: [],
  totals: {
    commits: 0,
    merged_requests: 0,
    reviews: 0,
    approvals: 0,
    additions: 0,
    deletions: 0,
    persons: 0,
    ai_percent: null,
  },
  validation: {
    total: 0,
    agent_review_rate: null,
    human_approval_rate: null,
    complete_rate: null,
    status: "not_measured",
  },
  sources: {},
};
const ownership = {
  project,
  window_days: 90,
  zones: [],
  alerts: [],
  status: "not_measured",
  sources: {},
};
const processData = {
  project,
  repositories: [],
  profiles: [],
  dominant_profile: null,
  project_profile: null,
  divergent: false,
  divergences: [],
  status: "not_measured",
};
const processFlow = { project, flows: [], gates: {}, sources: {} };

const deployments = {
  generated_at: "2026-10-21T10:00:00+00:00",
  project,
  filters: { env: null },
  environments: {
    dev: { status: "not_measured", count: 0, latest: null },
    preprod: { status: "not_measured", count: 0, latest: null },
    prod: { status: "not_measured", count: 0, latest: null },
  },
  history: [],
  total: 0,
  limit: 50,
  offset: 0,
  has_more: false,
  next_offset: null,
  rollbacks: [],
  dora: { metrics: [], deployments: { prod: 0, successful: 0, failed: 0 } },
  go_no_go: { verdict: "go", conditions: [], checklist: [] },
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
    if (url === "/api/projects/1/gates") {
      return Promise.resolve(jsonResponse(gates));
    }
    if (url.startsWith("/api/projects/1/findings")) {
      return Promise.resolve(jsonResponse(findings));
    }
    if (url === "/api/projects/1/review-packages") {
      return Promise.resolve(jsonResponse(reviewPackages));
    }
    if (url === "/api/projects/1/reviewers") {
      return Promise.resolve(jsonResponse(reviewers));
    }
    if (url === "/api/projects/1/decisions") {
      return Promise.resolve(jsonResponse(decisions));
    }
    if (url === "/api/projects/1/team") {
      return Promise.resolve(jsonResponse(team));
    }
    if (url.startsWith("/api/projects/1/team/ownership")) {
      return Promise.resolve(jsonResponse(ownership));
    }
    if (url === "/api/projects/1/process") {
      return Promise.resolve(jsonResponse(processData));
    }
    if (url === "/api/projects/1/process/flow") {
      return Promise.resolve(jsonResponse(processFlow));
    }
    if (url === "/api/projects/1/security") {
      return Promise.resolve(jsonResponse(security));
    }
    if (url === "/api/projects/1/performance") {
      return Promise.resolve(jsonResponse(quality));
    }
    if (url.startsWith("/api/projects/1/agents")) {
      return Promise.resolve(jsonResponse(agentsData));
    }
    if (url.startsWith("/api/projects/1/notifications")) {
      return Promise.resolve(jsonResponse(notifications));
    }
    if (url.startsWith("/api/projects/1/documents")) {
      return Promise.resolve(jsonResponse(documents));
    }
    if (url === "/api/projects/1/configuration") {
      return Promise.resolve(jsonResponse(configuration));
    }
    if (url.startsWith("/api/projects/1/deployments")) {
      return Promise.resolve(jsonResponse(deployments));
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

  it("expose le lien d'évitement et les 12 vues avec des titres de niveau 2", async () => {
    mockApi({ initiallyReady: true });
    render(<App />);

    expect(
      await screen.findByRole("link", { name: "Aller au contenu principal" }),
    ).toBeTruthy();
    expect(document.querySelector("main#main-content")).toBeTruthy();
    const expected = [
      "Vue d'ensemble",
      "Features & tâches",
      "Gates & qualité",
      "Revue indépendante",
      "Équipe",
      "Processus",
      "Sécurité",
      "Performance & données",
      "Agents IA",
      "Documentation",
      "Configuration",
      "Déploiements",
    ];
    for (const name of expected) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeTruthy();
    }
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
        if (url === "/api/projects/1/gates") {
          return Promise.resolve(jsonResponse(gates));
        }
        if (url.startsWith("/api/projects/1/findings")) {
          return Promise.resolve(jsonResponse(findings));
        }
        if (url === "/api/projects/1/review-packages") {
          return Promise.resolve(jsonResponse(reviewPackages));
        }
        if (url === "/api/projects/1/reviewers") {
          return Promise.resolve(jsonResponse(reviewers));
        }
        if (url === "/api/projects/1/decisions") {
          return Promise.resolve(jsonResponse(decisions));
        }
        if (url === "/api/projects/1/team") {
          return Promise.resolve(jsonResponse(team));
        }
        if (url.startsWith("/api/projects/1/team/ownership")) {
          return Promise.resolve(jsonResponse(ownership));
        }
        if (url === "/api/projects/1/process") {
          return Promise.resolve(jsonResponse(processData));
        }
        if (url === "/api/projects/1/process/flow") {
          return Promise.resolve(jsonResponse(processFlow));
        }
        if (url === "/api/projects/1/security") {
          return Promise.resolve(jsonResponse(security));
        }
        if (url === "/api/projects/1/performance") {
          return Promise.resolve(jsonResponse(quality));
        }
        if (url.startsWith("/api/projects/1/agents")) {
          return Promise.resolve(jsonResponse(agentsData));
        }
        if (url.startsWith("/api/projects/1/notifications")) {
          return Promise.resolve(jsonResponse(notifications));
        }
        if (url.startsWith("/api/projects/1/documents")) {
          return Promise.resolve(jsonResponse(documents));
        }
        if (url === "/api/projects/1/configuration") {
          return Promise.resolve(jsonResponse(configuration));
        }
        if (url.startsWith("/api/projects/1/deployments")) {
          return Promise.resolve(jsonResponse(deployments));
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
