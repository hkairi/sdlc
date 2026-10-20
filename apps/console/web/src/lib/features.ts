export type Phase = {
  id: string;
  name: string;
  status: string;
  source: string;
};

export type TaskSummary = {
  id: number;
  key: string;
  title: string;
  status: string;
  status_label: string;
  lot: string | null;
  executor: string | null;
  reviewer: string | null;
  updated_at: string | null;
  report_url: string;
};

export type Inconsistency = {
  id: number;
  feature_key: string;
  task_key: string;
  kind: string;
  message: string;
  state_status: string | null;
  tasks_md_checked: boolean | null;
  created_at: string | null;
};

export type FeatureItem = {
  id: number;
  key: string;
  name: string;
  status: string;
  status_label: string;
  phase: Phase;
  phase_id: string;
  phase_name: string;
  phase_status: string;
  objective: string | null;
  change: string | null;
  spec_path: string | null;
  tasks_file: string | null;
  sources: Record<string, string>;
  version: string | null;
  delivered: boolean;
  blocked: boolean;
  repositories: Array<{ id: number; name: string }>;
  tasks: TaskSummary[];
  task_summary: {
    total: number;
    done: number;
    doing: number;
    todo: number;
    blocked: number;
    progress_percent: number;
  };
  coverage: { status: string; value: unknown; label: string; source: string; detail: string };
  gate: { status: string; value: unknown; label: string; source: string; detail: string };
  executors: string[];
  reviewers: string[];
  updated_at: string | null;
  inconsistencies: Inconsistency[];
};

export type FeaturesResponse = {
  project: { id: number; name: string; slug: string };
  filters: { phase: string | null; gate: string | null };
  available_phases: Array<{ id: string; name: string }>;
  available_gates: Array<{ id: string; name: string; source: string }>;
  features: FeatureItem[];
  total: number;
  inconsistencies: Inconsistency[];
  sources: Record<string, string>;
};

export type TaskDetail = {
  id: number;
  key: string;
  title: string;
  description: string | null;
  status: string;
  status_label: string;
  lot: string | null;
  files: string[];
  acceptance: string | null;
  note: string | null;
  executor: string | null;
  reviewer: string | null;
  updated_at: string | null;
  feature: { id: number; key: string; name: string; phase: Phase };
  repositories: Array<{ id: number; name: string }>;
  report_url: string;
  report_available: boolean;
  source: string;
};

export function featuresUrl(projectId: number, phase: string, gate: string): string {
  const params = new URLSearchParams();
  if (phase) {
    params.set("phase", phase);
  }
  if (gate) {
    params.set("gate", gate);
  }
  const query = params.toString();
  return `/api/projects/${projectId}/features${query ? `?${query}` : ""}`;
}

export function taskDetailUrl(projectId: number, taskId: number): string {
  return `/api/projects/${projectId}/tasks/${taskId}`;
}
