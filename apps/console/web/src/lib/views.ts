export type ProjectRef = { id: number; name: string; slug: string };

export type SecurityFinding = {
  id: number;
  key: string;
  control: string;
  severity: string;
  message: string;
  file: string | null;
  line: number | null;
  evidence: string | null;
  waived: boolean;
  waivers: Array<{ id: number; status: string; reason: string }>;
};

export type SecurityView = {
  generated_at: string;
  project: ProjectRef;
  status: string;
  run: {
    id: number | null;
    verdict: string;
    base_verdict: string | null;
    blocks: boolean;
    report_path: string | null;
    generated_at: string | null;
  };
  findings: SecurityFinding[];
  finding_counts: Record<string, number>;
  sbom: {
    status: string;
    path: string | null;
    format: string | null;
    components: number | null;
    licenses: string[];
    packages: Array<{ name: string; version: string; licenses: string[] }>;
    detail: string;
  };
  licenses: {
    values: string[];
    count: number;
    status: string;
    policy: { allowed: string[]; denied: string[]; status: string };
  };
  waivers: Array<{
    id: number;
    gate_key: string;
    target_type: string;
    target_id: string | null;
    reason: string;
    owner: string;
    approver: string;
    expires_at: string;
    status: string;
  }>;
  agent_surface: {
    agents: Array<{ id: string; enabled: boolean; cli: string; models: string[] }>;
    repositories: Array<{ id: number; name: string; provider: string }>;
    recent_runs: Array<{
      run_id: string;
      agent_id: string | null;
      role: string | null;
      model: string | null;
      status: string;
      cost_eur: number | null;
      origin: string;
      log_url: string;
    }>;
    runs_by_status: Record<string, number>;
    read_only_reviews: number;
    git_write_refused: number;
    environment_policy: string;
    surface: string;
  };
  sources: Record<string, string>;
};

export function securityUrl(projectId: number): string {
  return `/api/projects/${projectId}/security`;
}

export type FindingRef = {
  id: number;
  key: string;
  control: string;
  severity: string;
  message: string;
  file: string | null;
  line: number | null;
  evidence: string | null;
};

export type QualityView = {
  generated_at: string;
  project: ProjectRef;
  performance: {
    status: string;
    verdict: string;
    blocks: boolean;
    report_path: string | null;
    generated_at: string | null;
    budgets: Record<string, number | null>;
    cases: Array<Record<string, unknown>>;
    signals: FindingRef[];
    findings: FindingRef[];
    controls: Array<Record<string, unknown>>;
  };
  data: {
    status: string;
    verdict: string;
    blocks: boolean;
    report_path: string | null;
    generated_at: string | null;
    controls: Array<Record<string, unknown>>;
    pii: FindingRef[];
    migrations: FindingRef[];
    backup: {
      status: string;
      verified: boolean | null;
      restore_tested: boolean | null;
      age_hours: number | null;
      source: string;
      verdict: string | null;
      reason: string | null;
    };
    retention_days: number | null;
    schema: {
      status: string;
      current: string | null;
      head: string | null;
      up_to_date: boolean | null;
      source: string;
      detail?: string;
    };
  };
  sources: Record<string, string>;
};

export function qualityUrl(projectId: number): string {
  return `/api/projects/${projectId}/performance`;
}

export type AgentRun = {
  id: number;
  run_id: string;
  task_key: string | null;
  agent_id: string | null;
  role: string | null;
  model: string | null;
  status: string;
  origin: string;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  cost_eur: number | null;
  estimated_cost_eur: number | null;
  budget_eur: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  log_path: string | null;
  failure_reason: string | null;
  events_url: string;
};

export type Independence = {
  status: string;
  window_days: number;
  total_reviews: number;
  independent_reviews: number;
  degraded_reviews: number;
  degraded_rate_percent: number | null;
  threshold_percent: number;
  decision_required: boolean;
  unmeasured_reviews: number;
  detail: string;
};

export type AgentsView = {
  project: ProjectRef;
  filters: { agent_id: string | null; role: string | null; status: string | null };
  runs: AgentRun[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  independence: Independence;
  independence_alert: {
    decision_required: boolean;
    notification_id: number;
    created: boolean;
    message: string;
  } | null;
};

export type HumanNotification = {
  id: number;
  kind: string;
  subject_type: string;
  subject_id: string;
  message: string;
  pending: boolean;
  created_at: string;
  acknowledged_at: string | null;
};

export type NotificationsView = {
  project: ProjectRef;
  notifications: HumanNotification[];
  total: number;
};

export function agentsUrl(
  projectId: number,
  filters: { agent: string; role: string; status: string } = { agent: "", role: "", status: "" },
): string {
  const params = new URLSearchParams();
  if (filters.agent) {
    params.set("agent_id", filters.agent);
  }
  if (filters.role) {
    params.set("role", filters.role);
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  const query = params.toString();
  return `/api/projects/${projectId}/agents${query ? `?${query}` : ""}`;
}

export function notificationsUrl(projectId: number): string {
  return `/api/projects/${projectId}/notifications?pending=true`;
}

export type DocumentItem = {
  key: string;
  label: string;
  path: string;
  exists: boolean;
  status: string;
  updated_at: string | null;
  age_days: number | null;
  review_days: number;
  generated: boolean;
  editable: boolean;
  notice: string | null;
  regenerate_url: string | null;
  link: string | null;
};

export type DocumentsView = {
  generated_at: string;
  project: ProjectRef;
  review_days: number;
  documents: DocumentItem[];
  summary: {
    expected: number;
    present: number;
    missing: number;
    stale: number;
    generated: number;
  };
  sources: Record<string, string>;
};

export type DocumentContent = {
  path: string;
  label: string;
  markdown: string | null;
  text: string;
  truncated: boolean;
  generated: boolean;
  editable: boolean;
  notice: string | null;
  regenerate_url: string | null;
  html_disabled: boolean;
  size_bytes: number;
};

export type DocumentsResponse = DocumentsView & { selected?: DocumentContent };

export function documentsUrl(projectId: number, path?: string): string {
  if (!path) {
    return `/api/projects/${projectId}/documents`;
  }
  const params = new URLSearchParams({ path });
  return `/api/projects/${projectId}/documents?${params.toString()}`;
}

export type ConfigurationView = {
  project: ProjectRef;
  config_file: { path: string; exists: boolean; readable: boolean };
  validation: {
    valid: boolean;
    errors: Array<{ path: string; message: string }>;
    schema_id: string | null;
    schema_title: string | null;
  };
  effective: Record<string, unknown>;
  origins: Array<{
    key: string;
    value: unknown;
    origin: string;
    source: string;
  }>;
  sources: Record<string, string>;
  notice: string;
};

export function configurationUrl(projectId: number): string {
  return `/api/projects/${projectId}/configuration`;
}

export type DeploymentItem = {
  id: number;
  deploy_id: string;
  environment: string;
  raw_environment: string;
  version: string | null;
  status: string;
  is_rollback: boolean;
  rollback_of_version: string | null;
  started_at: string | null;
  finished_at: string | null;
  by: string | null;
  repository: string | null;
  feature_key: string | null;
  note: string | null;
  origin: string;
};

export type ChecklistItem = {
  key: string;
  label: string;
  status: string;
  blocking: boolean;
  detail: string;
  evidence: string;
  source: string;
};

export type DeploymentsView = {
  generated_at: string;
  project: ProjectRef;
  filters: { env: string | null };
  environments: Record<
    string,
    { status: string; count: number; latest: DeploymentItem | null }
  >;
  history: DeploymentItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
  rollbacks: DeploymentItem[];
  dora: {
    metrics: Array<{
      key: string;
      label: string;
      value: number | null;
      unit: string | null;
      status: string;
      detail: string;
    }>;
    deployments: { prod: number; successful: number; failed: number };
  };
  go_no_go: {
    verdict: string;
    conditions: ChecklistItem[];
    checklist: ChecklistItem[];
  };
  sources: Record<string, string>;
};

export function deploymentsUrl(
  projectId: number,
  env = "",
  limit = 50,
  offset = 0,
): string {
  const params = new URLSearchParams();
  if (env) {
    params.set("env", env);
  }
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return `/api/projects/${projectId}/deployments?${params.toString()}`;
}
