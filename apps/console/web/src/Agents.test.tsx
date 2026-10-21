// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Agents from "./Agents";

const project = { id: 1, name: "Atlas", slug: "atlas" };
const agents = {
  project,
  filters: { agent_id: null, role: null, status: null },
  runs: [
    {
      id: 1,
      run_id: "run-1",
      task_key: "7.3",
      agent_id: "claude",
      role: "reviewer",
      model: "opus",
      status: "done",
      origin: "lancée",
      started_at: "2026-10-21T09:00:00+00:00",
      ended_at: "2026-10-21T09:00:12+00:00",
      duration_seconds: 12.5,
      cost_eur: 0.42,
      estimated_cost_eur: 0.4,
      budget_eur: 2,
      tokens_in: 100,
      tokens_out: 50,
      log_path: "reports/runs/run-1.log",
      failure_reason: null,
      events_url: "/api/runs/run-1/events",
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
  has_more: false,
  independence: {
    status: "measured",
    window_days: 30,
    total_reviews: 10,
    independent_reviews: 9,
    degraded_reviews: 1,
    degraded_rate_percent: 10,
    threshold_percent: 10,
    decision_required: true,
    unmeasured_reviews: 0,
    detail: "1/10 revue(s) dégradée(s)",
  },
  independence_alert: {
    decision_required: true,
    notification_id: 4,
    created: false,
    message: "Seuil d'indépendance atteint : 10 % de revues dégradées.",
  },
};
const notifications = {
  project,
  notifications: [
    {
      id: 4,
      kind: "review_escalation",
      subject_type: "task",
      subject_id: "7",
      message: "Tâche 7.3 bloquée après 3 rejets.",
      pending: true,
      created_at: "2026-10-21T09:00:00+00:00",
      acknowledged_at: null,
    },
  ],
  total: 1,
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
});

describe("Agents", () => {
  it("affiche runs, coûts, escalades et indépendance", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.startsWith("/api/projects/1/agents")) {
        return Promise.resolve(jsonResponse(agents));
      }
      if (url.startsWith("/api/projects/1/notifications")) {
        return Promise.resolve(jsonResponse(notifications));
      }
      return Promise.reject(new Error(`URL inattendue : ${url}`));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<Agents projectId={1} />);

    expect(await screen.findByText("Tâche 7.3 bloquée après 3 rejets.")).toBeTruthy();
    expect(screen.getByRole("table", { name: /Journal des runs/ })).toBeTruthy();
    expect(screen.getAllByText("0.42 €").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/10 %/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Décision humaine exigée/)).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Rôle"), { target: { value: "reviewer" } });
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/projects/1/agents?role=reviewer",
        expect.anything(),
      );
    });
  });
});
