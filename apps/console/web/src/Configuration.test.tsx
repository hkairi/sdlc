// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Configuration from "./Configuration";

const project = { id: 1, name: "Atlas", slug: "atlas" };
const payload = {
  project,
  config_file: { path: "sdlc.config.yaml", exists: true, readable: true },
  validation: {
    valid: true,
    errors: [],
    schema_id: "https://hmconsulting.local/config.schema.json",
    schema_title: "Configuration de la Console SDLC",
  },
  effective: { project: { name: "Atlas" }, agents: { claude: { enabled: true } } },
  origins: [
    {
      key: "project.name",
      value: "Atlas",
      origin: "déclarée",
      source: "sdlc.config.yaml",
    },
    {
      key: "features.count",
      value: 2,
      origin: "détectée",
      source: "base SQLite — features",
    },
    {
      key: "runs.count",
      value: 5,
      origin: "mesurée",
      source: "base SQLite — task_runs",
    },
  ],
  sources: { declared: "sdlc.config.yaml", detected: "base SQLite" },
  notice: "Configuration en lecture seule. Modifiez sdlc.config.yaml puis redémarrez.",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Configuration", () => {
  it("affiche la validation et les trois origines", async () => {
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
    render(<Configuration projectId={1} />);

    expect(await screen.findByText("Valide contre Configuration de la Console SDLC")).toBeTruthy();
    expect(screen.getAllByText("déclarée").length).toBeGreaterThan(0);
    expect(screen.getAllByText("détectée").length).toBeGreaterThan(0);
    expect(screen.getAllByText("mesurée").length).toBeGreaterThan(0);
    expect(screen.getByText(/base SQLite — task_runs/)).toBeTruthy();
    expect(screen.getByText(/lecture seule/)).toBeTruthy();
  });
});
