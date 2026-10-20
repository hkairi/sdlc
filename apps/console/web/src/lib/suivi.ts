export type Project = {
  id: number;
  name: string;
  slug: string;
};

export type SuiviSummary = {
  features: number;
  tasks: number;
  done: number;
  doing: number;
  todo: number;
  blocked: number;
  cancelled: number;
  progress_percent: number;
};

export type SuiviStatus = {
  ready: boolean;
  generated_at: string | null;
  html_path: string;
  json_path: string;
  stale: boolean;
  summary: SuiviSummary;
  open_on_ready: boolean;
  url: string;
};

export type StorageLike = Pick<Storage, "getItem" | "setItem">;
export type LocationLike = Pick<Location, "pathname" | "href">;
export type OpenFn = (url: string, target: string, features: string) => Window | null;

export function suiviStatusUrl(projectId: number): string {
  return `/api/projects/${projectId}/suivi/status`;
}

export function suiviUrl(projectId: number): string {
  return `/api/projects/${projectId}/suivi?format=html`;
}

export function suiviGenerationUrl(projectId: number): string {
  return `/api/projects/${projectId}/suivi?format=json`;
}

export function suiviOpenKey(projectId: number, generatedAt: string | null): string {
  return `sdlc.suivi.opened.${projectId}.${generatedAt ?? "ready"}`;
}

/**
 * Ouvre le suivi au plus une fois par génération.
 * Retourne true si un onglet a effectivement été demandé.
 */
export function openSuiviOnce(options: {
  projectId: number;
  status: SuiviStatus;
  storage?: StorageLike;
  location?: LocationLike;
  open?: OpenFn;
}): boolean {
  const { projectId, status } = options;
  if (!status.ready || !status.open_on_ready) {
    return false;
  }
  const storage = options.storage ?? window.localStorage;
  const location = options.location ?? window.location;
  if (location.pathname.includes("/suivi")) {
    return false;
  }
  const key = suiviOpenKey(projectId, status.generated_at);
  if (storage.getItem(key) === "1") {
    return false;
  }
  const opener = options.open ?? window.open;
  const handle = opener(status.url || suiviUrl(projectId), "_blank", "noopener,noreferrer");
  if (!handle) {
    return false;
  }
  storage.setItem(key, "1");
  return true;
}

export async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}
