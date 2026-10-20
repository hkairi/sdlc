export type Kpi = {
  key: string;
  label: string;
  value: string | number | null;
  unit: string | null;
  source: string;
  status: "measured" | "not_measured";
  detail: string;
};

export type PendingDecision = {
  id: string;
  kind: string;
  title: string;
  blocking: boolean;
  source: string;
  detail: string;
  link: string | null;
};

export type PipelineStage = {
  id: string;
  label: string;
  status: string;
  source: string;
  detail: string;
};

export type Risk = {
  category: string;
  severity: string;
  title: string;
  detail: string;
  source: string;
};

export type OverviewData = {
  generated_at: string;
  project: { id: number; name: string; slug: string };
  summary: {
    features: number;
    tasks: number;
    done: number;
    doing: number;
    todo: number;
    blocked: number;
  };
  kpis: Kpi[];
  pending_decisions: PendingDecision[];
  pending_decisions_source: string;
  pipeline: PipelineStage[];
  risks: Risk[];
  risk_categories?: Record<string, Risk[]>;
  risks_source: string;
};

export function overviewUrl(projectId: number): string {
  return `/api/projects/${projectId}/overview`;
}

export function formatKpiValue(kpi: Kpi): string {
  if (kpi.status === "not_measured" || kpi.value === null || kpi.value === undefined) {
    return "non mesuré";
  }
  return `${kpi.value}${kpi.unit ?? ""}`;
}

export function stageLabel(status: string): string {
  switch (status) {
    case "done":
      return "Terminé";
    case "doing":
      return "En cours";
    case "failed":
      return "Échec";
    case "todo":
      return "À faire";
    default:
      return "Non mesuré";
  }
}
