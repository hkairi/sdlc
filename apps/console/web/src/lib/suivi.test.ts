import { describe, expect, it, vi } from "vitest";
import {
  openSuiviOnce,
  suiviGenerationUrl,
  suiviOpenKey,
  suiviStatusUrl,
  suiviUrl,
  type SuiviStatus,
} from "./suivi";

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

function status(overrides: Partial<SuiviStatus> = {}): SuiviStatus {
  return {
    ready: true,
    generated_at: "2026-10-20T10:00:00+00:00",
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
    ...overrides,
  };
}

describe("suivi", () => {
  it("construit les URL du projet", () => {
    expect(suiviStatusUrl(4)).toBe("/api/projects/4/suivi/status");
    expect(suiviUrl(4)).toBe("/api/projects/4/suivi?format=html");
    expect(suiviGenerationUrl(4)).toBe("/api/projects/4/suivi?format=json");
    expect(suiviOpenKey(4, "2026-10-20T10:00:00+00:00")).toBe(
      "sdlc.suivi.opened.4.2026-10-20T10:00:00+00:00",
    );
  });

  it("ouvre une seule fois le suivi prêt", () => {
    const storage = new MemoryStorage();
    const open = vi.fn(() => ({}) as Window);
    const options = {
      projectId: 1,
      status: status(),
      storage,
      location: { pathname: "/", href: "http://127.0.0.2/" },
      open,
    };
    expect(openSuiviOnce(options)).toBe(true);
    expect(open).toHaveBeenCalledTimes(1);
    expect(open).toHaveBeenCalledWith(
      "/api/projects/1/suivi?format=html",
      "_blank",
      "noopener,noreferrer",
    );
    expect(openSuiviOnce(options)).toBe(false);
    expect(open).toHaveBeenCalledTimes(1);
  });

  it("n'ouvre pas si l'option est désactivée ou le suivi non prêt", () => {
    const storage = new MemoryStorage();
    const open = vi.fn(() => ({}) as Window);
    const base = {
      projectId: 1,
      storage,
      location: { pathname: "/", href: "http://127.0.0.2/" },
      open,
    };
    expect(openSuiviOnce({ ...base, status: status({ open_on_ready: false }) })).toBe(false);
    expect(openSuiviOnce({ ...base, status: status({ ready: false }) })).toBe(false);
    expect(open).not.toHaveBeenCalled();
  });

  it("n'ouvre pas depuis la vue Suivi elle-même", () => {
    const storage = new MemoryStorage();
    const open = vi.fn(() => ({}) as Window);
    const opened = openSuiviOnce({
      projectId: 1,
      status: status(),
      storage,
      location: { pathname: "/suivi", href: "http://127.0.0.2/suivi" },
      open,
    });
    expect(opened).toBe(false);
    expect(open).not.toHaveBeenCalled();
  });

  it("réouvre pour une nouvelle génération", () => {
    const storage = new MemoryStorage();
    const open = vi.fn(() => ({}) as Window);
    const location = { pathname: "/", href: "http://127.0.0.2/" };
    expect(openSuiviOnce({ projectId: 1, status: status(), storage, location, open })).toBe(true);
    expect(
      openSuiviOnce({
        projectId: 1,
        status: status({ generated_at: "2026-10-20T11:00:00+00:00" }),
        storage,
        location,
        open,
      }),
    ).toBe(true);
    expect(open).toHaveBeenCalledTimes(2);
  });

  it("ne marque pas comme ouverte si le navigateur bloque l'ouverture", () => {
    const storage = new MemoryStorage();
    const open = vi.fn(() => null);
    const opened = openSuiviOnce({
      projectId: 1,
      status: status(),
      storage,
      location: { pathname: "/", href: "http://127.0.0.2/" },
      open,
    });
    expect(opened).toBe(false);
    expect(storage.getItem(suiviOpenKey(1, status().generated_at))).toBeNull();
  });
});
