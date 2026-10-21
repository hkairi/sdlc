export type ReviewPackageItem = {
  id: number;
  task_key: string;
  feature_key: string | null;
  fingerprint: string;
  path: string;
  created_at: string;
};

export type ReviewPackagesResponse = {
  project: { id: number; name: string; slug: string };
  packages: ReviewPackageItem[];
  total: number;
};

export type ReviewerCandidate = {
  agent_id: string;
  model: string;
  family: string;
  label: string;
};

export type ReviewerResponse = {
  project: { id: number; name: string; slug: string };
  selected: ReviewerCandidate | null;
  level: string;
  allowed: boolean;
  waiver_required: boolean;
  reason: string;
  candidates: Array<Record<string, unknown>>;
};

export type DecisionItem = {
  id: number;
  subject_type: string;
  subject_id: string;
  decision: string;
  actor_label: string;
  reason: string;
  conditions: string[];
  scope: string | null;
  created_at: string;
  unauthenticated: boolean;
};

export type DecisionsResponse = {
  project: { id: number; name: string; slug: string };
  decisions: DecisionItem[];
  total: number;
};

export function reviewPackagesUrl(projectId: number): string {
  return `/api/projects/${projectId}/review-packages`;
}

export function reviewersUrl(projectId: number): string {
  return `/api/projects/${projectId}/reviewers`;
}

export function decisionsUrl(projectId: number): string {
  return `/api/projects/${projectId}/decisions`;
}
