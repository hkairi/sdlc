import { useEffect, useState } from "react";
import { fetchJson } from "./lib/suivi";
import {
  deploymentsUrl,
  type ChecklistItem,
  type DeploymentsView,
} from "./lib/views";

type Props = {
  projectId: number | null;
};

function metricValue(value: number | null, unit: string | null): string {
  return value === null ? "non mesuré" : `${value}${unit ? ` ${unit}` : ""}`;
}

function checklistClass(item: ChecklistItem): string {
  if (item.status === "pass") {
    return "badge badge-done";
  }
  if (item.status === "warn") {
    return "badge badge-warn";
  }
  return "badge badge-error";
}

export default function Deployments({ projectId }: Props) {
  const [data, setData] = useState<DeploymentsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [env, setEnv] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    if (projectId === null) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchJson<DeploymentsView>(deploymentsUrl(projectId, env, 50, offset))
      .then((next) => {
        if (!cancelled) {
          setData(next);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Vue Déploiements indisponible");
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
  }, [projectId, env, offset]);

  if (projectId === null) {
    return null;
  }

  return (
    <section className="card" aria-labelledby="deployments-title">
      <div className="card-head">
        <div>
          <h2 id="deployments-title">Déploiements</h2>
          <p className="muted">
            Dev, préprod et prod, historique, DORA, rollback et checklist go/no-go avec preuves.
          </p>
        </div>
        {data ? (
          <span
            className={`badge ${data.go_no_go.verdict === "go" ? "badge-done" : "badge-error"}`}
          >
            {data.go_no_go.verdict}
          </span>
        ) : null}
      </div>

      <div className="toolbar" aria-label="Filtres des déploiements">
        <label className="field" htmlFor="deployment-env">
          <span>Environnement</span>
          <select
            id="deployment-env"
            value={env}
            onChange={(event) => {
              setEnv(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">Tous</option>
            <option value="dev">Dev</option>
            <option value="preprod">Préprod</option>
            <option value="prod">Prod</option>
          </select>
        </label>
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement des déploiements…" : ""}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement des déploiements…</p> : null
      ) : (
        <>
          <div className="summary" aria-label="Environnements de déploiement">
            {(["dev", "preprod", "prod"] as const).map((key) => {
              const environment = data.environments[key];
              return (
                <div className="metric" key={key}>
                  <span className="metric-value">{environment.count}</span>
                  <span className="metric-label">{key}</span>
                  <span className="kpi-source">
                    {environment.latest
                      ? `dernier : ${environment.latest.version ?? environment.latest.deploy_id}`
                      : "non mesuré"}
                  </span>
                </div>
              );
            })}
          </div>

          <h3>Go / no-go</h3>
          {data.go_no_go.conditions.length > 0 ? (
            <div className="banner" role="alert">
              <strong>No-go : {data.go_no_go.conditions.length} condition(s) bloquante(s)</strong>
              <ul>
                {data.go_no_go.conditions.map((item) => (
                  <li key={item.key}>
                    {item.label} — {item.detail} ({item.evidence})
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="badge badge-done">Toutes les preuves bloquantes sont vertes.</p>
          )}
          <table className="data-table">
            <caption>Checklist go/no-go et preuves</caption>
            <thead>
              <tr>
                <th scope="col">Élément</th>
                <th scope="col">Statut</th>
                <th scope="col">Preuve</th>
                <th scope="col">Détail</th>
              </tr>
            </thead>
            <tbody>
              {data.go_no_go.checklist.map((item) => (
                <tr key={item.key}>
                  <td>{item.label}</td>
                  <td>
                    <span className={checklistClass(item)}>{item.status}</span>
                    {item.blocking ? <span className="kpi-source"> bloquant</span> : null}
                  </td>
                  <td>
                    <code>{item.evidence}</code>
                  </td>
                  <td className="muted">{item.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Métriques DORA</h3>
          <div className="overview-grid">
            {data.dora.metrics.map((metric) => (
              <div className="kpi" key={metric.key}>
                <span className="metric-label">{metric.label}</span>
                <span className="kpi-value">{metricValue(metric.value, metric.unit)}</span>
                {metric.status === "not_measured" ? (
                  <span className="badge badge-warn">non mesuré</span>
                ) : null}
                <span className="kpi-source">{metric.detail}</span>
              </div>
            ))}
          </div>

          <h3>Historique</h3>
          {data.history.length === 0 ? (
            <p className="muted">Aucun déploiement ne correspond au filtre.</p>
          ) : (
            <table className="data-table">
              <caption>Historique des déploiements</caption>
              <thead>
                <tr>
                  <th scope="col">Version</th>
                  <th scope="col">Environnement</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Date</th>
                  <th scope="col">Auteur</th>
                  <th scope="col">Rollback</th>
                </tr>
              </thead>
              <tbody>
                {data.history.map((deployment) => (
                  <tr key={deployment.id}>
                    <td>{deployment.version ?? deployment.deploy_id}</td>
                    <td>{deployment.environment}</td>
                    <td>
                      <span
                        className={`badge ${
                          deployment.status === "success" ? "badge-done" : "badge-error"
                        }`}
                      >
                        {deployment.status}
                      </span>
                    </td>
                    <td>{deployment.started_at ?? "non mesurée"}</td>
                    <td>{deployment.by ?? "—"}</td>
                    <td>
                      {deployment.is_rollback
                        ? `rollback de ${deployment.rollback_of_version ?? "version inconnue"}`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="pagination">
            <p className="muted">
              {data.history.length} / {data.total} déploiement(s) affiché(s)
            </p>
            <div className="toolbar">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - data.limit))}
              >
                Précédent
              </button>
              <button
                type="button"
                disabled={!data.has_more}
                onClick={() => setOffset(data.next_offset ?? offset)}
              >
                Suivant
              </button>
            </div>
          </div>

          <h3>Rollbacks</h3>
          {data.rollbacks.length === 0 ? (
            <p className="muted">Aucun rollback ingéré.</p>
          ) : (
            <ul className="compact-list">
              {data.rollbacks.map((deployment) => (
                <li key={deployment.id}>
                  <span className="badge badge-error">rollback</span>{" "}
                  <strong>{deployment.version ?? deployment.deploy_id}</strong>
                  <span className="muted">
                    {" "}
                    — retour à {deployment.rollback_of_version ?? "version inconnue"} le{" "}
                    {deployment.started_at ?? "date non mesurée"}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="kpi-source">
            Sources :{" "}
            {Object.entries(data.sources)
              .map(([key, value]) => `${key} = ${value}`)
              .join(" · ")}
          </p>
        </>
      )}
    </section>
  );
}
