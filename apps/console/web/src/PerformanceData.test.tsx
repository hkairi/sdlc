// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PerformanceData from "./PerformanceData";

const project = { id: 1, name: "Atlas", slug: "atlas" };
const finding = {
  id: 1,
  key: "data:pii:app.log:3",
  control: "pii",
  severity: "error",
  message: "PII en clair dans les logs : alice@example.com",
  file: "reports/data/logs/app.log",
  line: 3,
  evidence: null,
};

const payload = {
  generated_at: "2026-10-21T10:00:00+00:00",
  project,
  performance: {
    status: "measured",
    verdict: "warn",
    blocks: false,
    report_path: "reports/gates/performance.json",
    generated_at: "2026-10-21T10:00:00+00:00",
    budgets: { default_p95_ms: 300 },
    cases: [{ case: "/search", p50_ms: 100, p95_ms: 120, p99_ms: 160, budget_ms: 300, commit: "abc" }],
    signals: [
      {
        ...finding,
        id: 2,
        key: "perf:static:unbounded_query",
        control: "static",
        severity: "warning",
        message: "requête non bornée",
        file: "src/repo.py",
        line: 12,
      },
    ],
    findings: [],
    controls: [],
  },
  data: {
    status: "measured",
    verdict: "fail",
    blocks: true,
    report_path: "reports/gates/data.json",
    generated_at: "2026-10-21T10:00:00+00:00",
    controls: [],
    pii: [finding],
    migrations: [],
    backup: {
      status: "measured",
      verified: true,
      restore_tested: true,
      age_hours: 2,
      source: "reports/data/backup.json",
      verdict: "pass",
      reason: "sauvegarde vérifiée et restauration testée",
    },
    retention_days: 365,
    schema: {
      status: "measured",
      current: "0020",
      head: "0020",
      up_to_date: true,
      source: "alembic",
    },
  },
  sources: { performance: "reports/perf/*.json", data: "reports/data/*" },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PerformanceData", () => {
  it("affiche budgets, cas, signaux, PII, migrations et sauvegarde", async () => {
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
    render(<PerformanceData projectId={1} />);

    expect(await screen.findByText("/search")).toBeTruthy();
    expect(screen.getByText(/requête non bornée/)).toBeTruthy();
    expect(screen.getByText(/alice@example.com/)).toBeTruthy();
    expect(screen.getByText("sauvegarde vérifiée et restauration testée")).toBeTruthy();
    expect(screen.getByText(/365 jour/)).toBeTruthy();
    expect(screen.getByRole("table", { name: /Cas de performance/ })).toBeTruthy();
  });
});
