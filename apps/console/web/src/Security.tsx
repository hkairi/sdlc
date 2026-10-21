import { useEffect, useState } from "react";
import { fetchJson } from "./lib/suivi";
import { securityUrl, type SecurityView } from "./lib/views";

type Props = {
  projectId: number | null;
};

function severityClass(severity: string): string {
  if (severity === "critical" || severity === "error") {
    return "badge badge-error";
  }
  if (severity === "warning" || severity === "warn") {
    return "badge badge-warn";
  }
  return "badge";
}

export default function Security({ projectId }: Props) {
  const [data, setData] = useState<SecurityView | null>(null);
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
    fetchJson<SecurityView>(securityUrl(projectId))
      .then((next) => {
        if (!cancelled) {
          setData(next);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Vue Sécurité indisponible");
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

  return (
    <section className="card" aria-labelledby="security-title">
      <div className="card-head">
        <div>
          <h2 id="security-title">Sécurité</h2>
          <p className="muted">
            Findings, SBOM, licences, dérogations et surface agentique du dernier gate.
          </p>
        </div>
        {data ? (
          <p className={`badge ${data.run.blocks ? "badge-error" : "badge-done"}`}>
            {data.run.verdict}
          </p>
        ) : null}
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement de la sécurité…" : ""}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement de la sécurité…</p> : null
      ) : (
        <>
          <div className="summary" aria-label="Indicateurs de sécurité">
            {["critical", "error", "warning", "info"].map((severity) => (
              <div className="metric" key={severity}>
                <span className="metric-value">{data.finding_counts[severity] ?? 0}</span>
                <span className="metric-label">{severity}</span>
              </div>
            ))}
            <div className="metric">
              <span className="metric-value">{data.licenses.count}</span>
              <span className="metric-label">Licences</span>
            </div>
          </div>

          <h3>Findings</h3>
          {data.findings.length === 0 ? (
            <p className="muted">
              Aucun finding sur le dernier run.{" "}
              {data.status === "not_measured" ? "Le gate sécurité n'a pas encore de preuve." : ""}
            </p>
          ) : (
            <table className="data-table">
              <caption>Findings du dernier run de sécurité</caption>
              <thead>
                <tr>
                  <th scope="col">Sévérité</th>
                  <th scope="col">Finding</th>
                  <th scope="col">Emplacement</th>
                  <th scope="col">Dérogation</th>
                </tr>
              </thead>
              <tbody>
                {data.findings.map((finding) => (
                  <tr key={finding.id}>
                    <td>
                      <span className={severityClass(finding.severity)}>{finding.severity}</span>
                    </td>
                    <td>
                      <strong>{finding.key}</strong>
                      <span className="muted"> — {finding.message}</span>
                    </td>
                    <td>
                      {finding.file ? (
                        <code>
                          {finding.file}
                          {finding.line ? `:${finding.line}` : ""}
                        </code>
                      ) : (
                        <span className="muted">non localisé</span>
                      )}
                    </td>
                    <td>
                      {finding.waived ? (
                        <span className="badge badge-warn">dérogation active</span>
                      ) : (
                        <span className="muted">aucune</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="view-grid">
            <div>
              <h3>SBOM</h3>
              {data.sbom.status === "measured" ? (
                <>
                  <p>
                    <strong>{data.sbom.format}</strong> · {data.sbom.components} composant(s)
                  </p>
                  <p className="kpi-source">Source : {data.sbom.path}</p>
                  <p>
                    Licences :{" "}
                    {data.licenses.values.length > 0
                      ? data.licenses.values.join(", ")
                      : "aucune licence déclarée"}
                  </p>
                  <p className="muted">
                    Politique : {data.licenses.policy.status}
                    {data.licenses.policy.allowed.length > 0
                      ? ` · autorisées : ${data.licenses.policy.allowed.join(", ")}`
                      : ""}
                  </p>
                </>
              ) : (
                <p className="badge badge-warn">{data.sbom.detail}</p>
              )}
            </div>

            <div>
              <h3>Dérogations</h3>
              {data.waivers.length === 0 ? (
                <p className="muted">Aucune dérogation de sécurité.</p>
              ) : (
                <ul className="compact-list">
                  {data.waivers.map((waiver) => (
                    <li key={waiver.id}>
                      <span className={`badge badge-${waiver.status === "active" ? "warn" : "error"}`}>
                        {waiver.status}
                      </span>{" "}
                      <strong>{waiver.target_type}</strong>{" "}
                      <span className="muted">— {waiver.reason}</span>
                      <span className="kpi-source">
                        {" "}
                        expire le {waiver.expires_at} · approbateur {waiver.approver}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <h3>Surface agentique</h3>
          <p className="muted">{data.agent_surface.environment_policy}</p>
          <div className="summary">
            <div className="metric">
              <span className="metric-value">{data.agent_surface.read_only_reviews}</span>
              <span className="metric-label">Revues lecture seule</span>
            </div>
            <div className="metric">
              <span className="metric-value">{data.agent_surface.git_write_refused}</span>
              <span className="metric-label">Git refusé</span>
            </div>
            <div className="metric">
              <span className="metric-value">{data.agent_surface.repositories.length}</span>
              <span className="metric-label">Dépôts exposés</span>
            </div>
          </div>
          {data.agent_surface.agents.length === 0 ? (
            <p className="muted">Aucun agent activé dans la configuration.</p>
          ) : (
            <ul className="compact-list">
              {data.agent_surface.agents.map((agent) => (
                <li key={agent.id}>
                  <strong>{agent.id}</strong>{" "}
                  <span className={`badge ${agent.enabled ? "badge-done" : "badge-warn"}`}>
                    {agent.enabled ? "activé" : "désactivé"}
                  </span>{" "}
                  <code>{agent.cli || "CLI non déclarée"}</code>{" "}
                  <span className="muted">
                    modèles : {agent.models.length > 0 ? agent.models.join(", ") : "non mesurés"}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="kpi-source">
            Sources : {Object.entries(data.sources).map(([key, value]) => `${key} = ${value}`).join(" · ")}
          </p>
        </>
      )}
    </section>
  );
}
