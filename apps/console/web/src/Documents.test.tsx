// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Documents from "./Documents";

const project = { id: 1, name: "Atlas", slug: "atlas" };
const brief = {
  key: "brief",
  label: "Brief",
  path: "docs/00-cadrage/brief.md",
  exists: true,
  status: "stale",
  updated_at: "2026-08-01T10:00:00+00:00",
  age_days: 80,
  review_days: 30,
  generated: false,
  editable: true,
  notice: null,
  regenerate_url: null,
  link: "/api/projects/1/documents?path=docs%2F00-cadrage%2Fbrief.md",
};
const generated = {
  ...brief,
  key: "generated",
  label: "Document généré",
  path: "docs/suivi-console.html",
  status: "fresh",
  age_days: 1,
  generated: true,
  editable: false,
  notice: "Fichier généré, ne pas modifier.",
  regenerate_url: "/api/projects/1/suivi?format=json",
};
const listing = {
  generated_at: "2026-10-21T10:00:00+00:00",
  project,
  review_days: 30,
  documents: [brief, generated],
  summary: { expected: 2, present: 2, missing: 0, stale: 1, generated: 1 },
  sources: { documents: "docs/" },
};
const selected = {
  path: "docs/00-cadrage/brief.md",
  label: "Brief",
  markdown: "# Brief\n\n<html><script>alert(1)</script>\n",
  text: "# Brief",
  truncated: false,
  generated: false,
  editable: true,
  notice: null,
  regenerate_url: null,
  html_disabled: true,
  size_bytes: 42,
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

describe("Documents", () => {
  it("liste la fraîcheur et rend le Markdown sans interpréter le HTML", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url === "/api/projects/1/documents") {
        return Promise.resolve(jsonResponse(listing));
      }
      if (url.startsWith("/api/projects/1/documents?path=")) {
        return Promise.resolve(jsonResponse({ ...listing, selected }));
      }
      return Promise.reject(new Error(`URL inattendue : ${url}`));
    });
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(<Documents projectId={1} />);

    expect(await screen.findByText("Brief")).toBeTruthy();
    expect(screen.getByText("à revoir")).toBeTruthy();
    expect(screen.getByText("fichier généré")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Lire Brief/ }));
    expect(await screen.findByText(/<script>alert\(1\)<\/script>/)).toBeTruthy();
    expect(container.querySelector("script")).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/projects/1/documents?path=docs%2F00-cadrage%2Fbrief.md",
      expect.anything(),
    );
  });
});
