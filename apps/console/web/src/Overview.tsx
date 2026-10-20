import { useEffect, useState } from "react";
import {
  formatKpiValue,
  overviewUrl,
  stageLabel,
  type OverviewData,
} from "./lib/overview";
import { fetchJson } from "./lib/suivi";

type Props = {
  projectId: number | null;
};

export default function Overview({ projectId }: Props) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (projectId === null) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchJson<OverviewData>(overviewUrl(projectId))
      .then((next) => {
        if (!cancelled) {
          setData(next);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            cause instanceof Error ? cause.message : "Vue d'ensemble indisponible",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (projectId === null) {
    return null;
  }

  const decisions = [...(data?.pending_decisions ?? [])].sort((left, right) => {
    if (left.blocking !== right.blocking) {
      return left.blocking ? -1 : 1;
    }
    return left.title.localeCompare(right.title, "fr");
  });
  const risksByCategory = new Map<string, OverviewData["risks"]>(
    data?.risk_categories ? Object.entries(data.risk_categories) : [],
  );
  for (const risk of data?.risks ?? []) {
    if (!risksByCategory.has(risk.category)) {
      risksByCategory.set(risk.category, []);
    }
    const group = risksByCategory.get(risk.category) ?? [];
    if (!group.includes(risk)) {
      group.push(risk);
    }
  }

  return (
    <section className="card" aria-labelledby="overview-title">
      <div className="card-head">
        <div>
          <h2 id="overview-title">Vue d'ensemble</h2>
          <p className="muted">
            Chaque indicateur affiche sa source ; une mesure absente reste « non mesuré ».
          </p>
        </div>
        {data ? (
          <p className="muted">
            {data.summary.features} feature(s) · {data.summary.tasks} tâche(s) ·{" "}
            {data.summary.blocked} bloquée(s)
          </p>
        ) : null}
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement de la vue d'ensemble…" : ""}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement de la vue d'ensemble…</p> : null
      ) : (
        <>
          <h3>Indicateurs clés</h3>
          <div className="overview-grid" aria-label="Indicateurs clés">
            {data.kpis.map((kpi) => (
              <div className="kpi" key={kpi.key}>
                <span className="metric-label">{kpi.label}</span>
                <span className="kpi-value">{formatKpiValue(kpi)}</span>
                {kpi.status === "not_measured" ? (
                  <span className="badge badge-warn">non mesuré</span>
                ) : null}
                <span className="kpi-source">Source : {kpi.source}</span>
                <span className="kpi-detail">{kpi.detail}</span>
              </div>
            ))}
          </div>

          <h3>Décisions en attente</h3>
          {decisions.length === 0 ? (
            <p className="muted">Aucune décision en attente.</p>
          ) : (
            <ul className="decision-list">
              {decisions.map((decision) => (
                <li key={decision.id}>
                  <span className={decision.blocking ? "badge badge-error" : "badge"}>
                    {decision.blocking ? "Bloquant" : "À suivre"}
                  </span>{" "}
                  <strong>{decision.title}</strong>
                  <span className="muted"> — {decision.detail}</span>
                  <span className="kpi-source"> Source : {decision.source}</span>
                  {decision.link ? (
                    <>
                      {" "}
                      <a href={decision.link}>Ouvrir la preuve</a>
                    </>
                  ) : (
                    <span className="kpi-source"> Preuve non disponible</span>
                  )}
                </li>
              ))}
            </ul>
          )}

          <h3>Pipeline SDLC</h3>
          <ol className="pipeline" aria-label="Pipeline SDLC">
            {data.pipeline.map((stage) => (
              <li className={`stage stage-${stage.status}`} key={stage.id}>
                <span className="stage-label">{stage.label}</span>
                <span className={`badge badge-${stage.status}`}>{stageLabel(stage.status)}</span>
                <span className="kpi-source">
                  Source : {stage.source}
                  {stage.detail ? ` — ${stage.detail}` : ""}
                </span>
              </li>
            ))}
          </ol>

          <h3>Risques par catégorie</h3>
          {risksByCategory.size === 0 ? (
            <p className="muted">Aucun risque ouvert mesuré.</p>
          ) : (
            <div className="risk-groups">
              {Array.from(risksByCategory.entries()).map(([category, risks]) => (
                <div className="risk-group" key={category}>
                  <h4>{category}</h4>
                  {risks.length === 0 ? (
                    <p className="muted">Aucun risque mesuré.</p>
                  ) : (
                    <ul>
                      {risks.map((risk) => (
                        <li key={`${risk.category}-${risk.title}`}>
                          <span className="badge badge-warn">{risk.severity}</span>{" "}
                          <strong>{risk.title}</strong>
                          <span className="muted"> — {risk.detail}</span>
                          <span className="kpi-source"> Source : {risk.source}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
          <p className="kpi-source">
            Généré le <time dateTime={data.generated_at}>{data.generated_at}</time>
          </p>
        </>
      )}
    </section>
  );
}
