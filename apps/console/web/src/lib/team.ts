export type TeamTotals = {
  commits: number;
  merged_requests: number;
  reviews: number;
  approvals: number;
  additions: number;
  deletions: number;
  persons: number;
  ai_percent: number | null;
  ai_status?: string;
};

export type TeamRepository = {
  repository_id: number;
  repository_name: string;
  commits: number;
  merged_requests: number;
  reviews: number;
  approvals: number;
  additions: number;
  deletions: number;
  persons: number;
};

export type TeamPerson = {
  person: { id: number; display_name: string; role: string | null; is_bot: boolean };
  commits: number;
  merged_requests: number;
  reviews: number;
  approvals: number;
  additions: number;
  deletions: number;
  last_activity: string | null;
};

export type TeamResponse = {
  project: { id: number; name: string; slug: string };
  repositories: TeamRepository[];
  persons: TeamPerson[];
  totals: TeamTotals;
  validation: {
    total: number;
    agent_review_rate: number | null;
    human_approval_rate: number | null;
    complete_rate: number | null;
    status: string;
  };
  sources: Record<string, string>;
};

export type OwnershipZone = {
  zone: string;
  repository_name: string;
  declared_owners: string[];
  owners: string[];
  commits: number;
  bus_factor: number;
  risk: boolean;
  primary_owner: { name: string; commits: number; share: number } | null;
  status: string;
};

export type OwnershipResponse = {
  project: { id: number; name: string; slug: string };
  window_days: number;
  zones: OwnershipZone[];
  alerts: Array<{ zone: string; severity: string; message: string }>;
  status: string;
  sources: Record<string, string>;
};

export function teamUrl(projectId: number): string {
  return `/api/projects/${projectId}/team`;
}

export function ownershipUrl(projectId: number): string {
  return `/api/projects/${projectId}/team/ownership`;
}
