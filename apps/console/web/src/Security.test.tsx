// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Security from "./Security";

const project = { id: 1, name: "Atlas", slug: "atlas" };

const payload = {
  generated_at: "2026-10-21T10:00:00+00:00",
  project,
  status: "measured",
  run: {
    id: 3,
    verdict: "fail",
    base_verdict: "fail",
    blocks: true,
    report_path: "reports/gates/security.json",
    generated_at: "2026-10-21T10:00:00+00:00",
  },
  findings: [
    {
      id: 1,
      key: "CVE-2026-4242",
      control: "vulnerabilities",
      severity: "error",
      message: "CVE haute atteignable",
      file: "src/app.py",
      line: 42,
      evidence: "reports/security/sast.sarif",
      waived: false,
      waivers: [],
    },
  ],
  finding_counts: { critical: 0, error: 1, warning: 0, info: 0 },
  sbom: {
    status: "measured",
    path: "reports/security/sbom.json",
    format: "cyclonedx",
    components: 2,
    licenses: ["MIT", "Propriétaire"],
    packages: [],
    detail: "2 composant(s), 2 licence(s)",
  },
  licenses: {
    values: ["MIT", "Propriétaire"],
    count: 2,
    status: "measured",
    policy: { allowed: [], denied: [], status: "not_declared" },
  },
  waivers: [],
  agent_surface: {
    agents: [
      { id: "claude", enabled: true, cli: "claude -p", models: ["think", "build"] },
    ],
    repositories: [{ id: 1, name: "atlas", provider: "github" }],
    recent_runs: [],
    runs_by_status: {},
    read_only_reviews: 1,
    git_write_refused: 2,
    environment_policy: "jetons purgés ; Git en écriture refusé ; revue en lecture seule",
    surface: "modèles de commande configurés uniquement",
  },
  sources: { gate: "reports/gates/security.json", sbom: "reports/security/sbom.json" },
};

function jsonResponse(payloadValue: unknown): Response {
  return new Response(JSON.stringify(payloadValue), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Security", () => {
  it("affiche findings, SBOM, licences et surface agentique", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse(payload))));
    render(<Security projectId={1} />);

    expect(await screen.findByText("CVE-2026-4242")).toBeTruthy();
    expect(screen.getByText(/src\/app.py:42/)).toBeTruthy();
    expect(screen.getByText(/MIT/)).toBeTruthy();
    expect(screen.getByText(/Git refusé/)).toBeTruthy();
    expect(screen.getByText(/claude -p/)).toBeTruthy();
    expect(screen.getByRole("table", { name: /Findings du dernier run/ })).toBeTruthy();
  });
});
