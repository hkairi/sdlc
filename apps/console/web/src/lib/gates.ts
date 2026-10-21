export type GateWaiver = {
  id: number;
  gate_key: string;
  target_type: string;
  target_id: string | null;
  reason: string;
  owner: string;
  approver: string;
  expires_at: string;
  status: string;
  active: boolean;
};

export type GateItem = {
  gate_key: string;
  name: string;
  verdict: string;
  base_verdict: string;
  blocks: boolean;
  reason: string;
  report_path: string;
  config_fingerprint: string | null;
  created_at: string | null;
  findings_count: number;
  controls: Array<{
    key: string;
    verdict: string;
    reason: string;
    details?: Record<string, unknown>;
  }>;
  waiver: GateWaiver | null;
  waivers: GateWaiver[];
  recalculate_required: boolean;
};

export type GatesResponse = {
  project: { id: number; name: string; slug: string };
  gates: GateItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
};

export type FindingItem = {
  id: number;
  gate_run_id: number;
  control: string;
  key: string;
  severity: string;
  message: string;
  file: string | null;
  line: number | null;
  evidence: string | null;
};

export type FindingsResponse = {
  project: { id: number; name: string; slug: string };
  findings: FindingItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
};

export function gatesUrl(projectId: number): string {
  return `/api/projects/${projectId}/gates`;
}

export function findingsUrl(projectId: number, limit = 50): string {
  return `/api/projects/${projectId}/findings?limit=${limit}`;
}
