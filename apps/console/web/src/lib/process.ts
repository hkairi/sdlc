export type ProcessRepository = {
  repository_id: number;
  repository_name: string;
  profile: string;
  label: string;
  confidence: number | null;
  detected: boolean;
  source: string;
  detected_profile: { key: string; label: string; confidence: number | null };
  override: { reason: string; actor_label: string; created_at: string } | null;
};

export type ProcessResponse = {
  project: { id: number; name: string; slug: string };
  repositories: ProcessRepository[];
  profiles: Array<{ key: string; label: string; count: number }>;
  dominant_profile: { key: string; label: string; count: number; total: number } | null;
  project_profile: { key: string; label: string; source: string } | null;
  divergent: boolean;
  divergences: Array<{ key: string; label: string; count: number; repositories: string[] }>;
  status: string;
};

export type ProcessFlowStep = {
  id: string;
  label: string;
  type: string;
  status: string;
  gate_key?: string;
  blocks?: boolean;
  evidence?: string | null;
};

export type ProcessFlowResponse = {
  project: { id: number; name: string; slug: string };
  flows: Array<{ id: string; label: string; steps: ProcessFlowStep[] }>;
  gates: Record<string, unknown>;
  sources: Record<string, string>;
};

export function processUrl(projectId: number): string {
  return `/api/projects/${projectId}/process`;
}

export function processFlowUrl(projectId: number): string {
  return `/api/projects/${projectId}/process/flow`;
}
