// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Deployments from "./Deployments";

const project = { id: 1, name: "Atlas", slug: "atlas" };
const deployment = {
  id: 1,
  deploy_id: "deploy-1",
  environment: "prod",
  raw_environment: "production",
  version: "v1",
  status: "success",
  is_rollback: false,
  rollback_of_version: null,
  started_at: "2026-10-21T09:00:00+00:00",
  finished_at: null,
  by: "alice",
  repository: "atlas",
  feature_key: "F-1",
  note: null,
  origin: "deploys.jsonl",
};
const checklist = [
  {
    key: "tests",
    label: "Tests",
    status: "pass",
    blocking: true,
    detail: "preuve fournie",
    evidence: "reports/gates/tests.json",
    source: "reports/gates",
  },
  {
    key: "recette",
    label: "Recette",
    status: "fail",
    blocking: true,
    detail: "aucune recette",
    evidence: "docs/recette",
    source: "docs/recette",
  },
];
const payload = {
  generated_at: "2026-10-21T10:00:00+00:00",
  project,
  filters: { env: null },
  environments: {
    dev: { status: "measured", count: 1, latest: deployment },
    preprod: { status: "measured", count: 1, latest: deployment },
    prod: { status: "measured", count: 1, latest: deployment },
  },
  history: [deployment],
  total: 1,
  limit: 50,
  offset: 0,
  has_more: false,
  next_offset: null,
  rollbacks: [],
  dora: {
    metrics: [
      {
        key: "change_failure_rate",
        label: "Change failure rate",
        value: 12.5,
        unit: "%",
        status: "measured",
        detail: "1 échec sur 8",
      },
    ],
    deployments: { prod: 1, successful: 1, failed: 0 },
  },
  go_no_go: {
    verdict: "no-go",
    conditions: [checklist[1]],
    checklist,
  },
  sources: { deployments: "docs/journal/deploys.jsonl" },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Deployments", () => {
  it("affiche environnements, DORA, historique et no-go", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(payload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    render(<Deployments projectId={1} />);

    expect(await screen.findByText("No-go : 1 condition(s) bloquante(s)")).toBeTruthy();
    expect(screen.getByText("v1")).toBeTruthy();
    expect(screen.getByText("12.5 %")).toBeTruthy();
    expect(screen.getByRole("table", { name: /Historique des déploiements/ })).toBeTruthy();
    expect(screen.getByRole("table", { name: /Checklist go\/no-go/ })).toBeTruthy();
    expect(screen.getAllByText(/docs\/recette/).length).toBeGreaterThan(0);
  });
});
