// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Gates from "./Gates";
import Process from "./Process";
import Review from "./Review";
import Team from "./Team";

const project = { id: 1, name: "Atlas", slug: "atlas" };

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

describe("vues de qualité, revue, équipe et processus", () => {
  it("rend la vue Gates avec un état non mesuré explicite", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url === "/api/projects/1/gates") {
          return Promise.resolve(
            jsonResponse({
              project,
              gates: [],
              total: 0,
              limit: 50,
              offset: 0,
              has_more: false,
              next_offset: null,
            }),
          );
        }
        return Promise.resolve(
          jsonResponse({
            project,
            findings: [],
            total: 0,
            limit: 50,
            offset: 0,
            has_more: false,
            next_offset: null,
          }),
        );
      }),
    );
    render(<Gates projectId={1} />);
    expect(await screen.findByRole("heading", { name: "Gates & qualité" })).toBeTruthy();
    expect(screen.getByText(/Aucun gate exécuté/)).toBeTruthy();
  });

  it("rend la vue Revue avec l'indépendance et les paquets", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url === "/api/projects/1/review-packages") {
          return Promise.resolve(jsonResponse({ project, packages: [], total: 0 }));
        }
        if (url === "/api/projects/1/reviewers") {
          return Promise.resolve(
            jsonResponse({
              project,
              selected: null,
              level: "degraded",
              allowed: false,
              waiver_required: true,
              reason: "aucun relecteur",
              candidates: [],
            }),
          );
        }
        return Promise.resolve(jsonResponse({ project, decisions: [], total: 0 }));
      }),
    );
    render(<Review projectId={1} />);
    expect(await screen.findByRole("heading", { name: "Revue indépendante" })).toBeTruthy();
    expect(screen.getByText("aucun relecteur")).toBeTruthy();
    expect(screen.getByText("Aucun paquet de revue.")).toBeTruthy();
  });

  it("rend la vue Équipe avec bus factor et personnes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url === "/api/projects/1/team") {
          return Promise.resolve(
            jsonResponse({
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
            }),
          );
        }
        return Promise.resolve(
          jsonResponse({
            project,
            window_days: 90,
            zones: [],
            alerts: [],
            status: "not_measured",
            sources: {},
          }),
        );
      }),
    );
    render(<Team projectId={1} />);
    expect(await screen.findByRole("heading", { name: "Équipe" })).toBeTruthy();
    expect(screen.getByText(/Non mesurée : aucune MR/)).toBeTruthy();
    expect(screen.getByText(/Aucune zone CODEOWNERS/)).toBeTruthy();
  });

  it("rend la vue Processus avec le flux et les gates", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url === "/api/projects/1/process") {
          return Promise.resolve(
            jsonResponse({
              project,
              repositories: [],
              profiles: [],
              dominant_profile: null,
              project_profile: null,
              divergent: false,
              divergences: [],
              status: "not_measured",
            }),
          );
        }
        return Promise.resolve(jsonResponse({ project, flows: [], gates: {}, sources: {} }));
      }),
    );
    render(<Process projectId={1} />);
    expect(await screen.findByRole("heading", { name: "Processus" })).toBeTruthy();
    expect(screen.getByText(/Profil projet/)).toBeTruthy();
    expect(screen.getByText(/Flux et gates/)).toBeTruthy();
  });
});
