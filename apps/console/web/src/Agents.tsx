import { useEffect, useState } from "react";
import RunLog from "./RunLog";
import { fetchJson } from "./lib/suivi";
import {
  agentsUrl,
  notificationsUrl,
  type AgentsView,
  type AgentRun,
  type NotificationsView,
} from "./lib/views";

type Props = {
  projectId: number | null;
};

function duration(run: AgentRun): string {
  if (run.duration_seconds === null) {
    return "non mesurée";
  }
  return `${run.duration_seconds.toFixed(1)} s`;
}

function cost(run: AgentRun): string {
  if (run.cost_eur === null) {
    return "non mesuré";
  }
  return `${run.cost_eur.toFixed(2)} €`;
}

export default function Agents({ projectId }: Props) {
  const [data, setData] = useState<AgentsView | null>(null);
  const [notifications, setNotifications] = useState<NotificationsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [agent, setAgent] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<AgentRun | null>(null);

  useEffect(() => {
    if (projectId === null) {
      setData(null);
      setNotifications(null);
      setSelected(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchJson<AgentsView>(agentsUrl(projectId, { agent, role, status })),
      fetchJson<NotificationsView>(notificationsUrl(projectId)),
    ])
      .then(([next, alerts]) => {
        if (!cancelled) {
          setData(next);
          setNotifications(alerts);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Vue Agents IA indisponible");
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
  }, [projectId, agent, role, status]);

  if (projectId === null) {
    return null;
  }

  const pageCost =
    data?.runs.reduce((total, run) => total + (run.cost_eur ?? 0), 0) ?? 0;
  const pageTokensIn =
    data?.runs.reduce((total, run) => total + (run.tokens_in ?? 0), 0) ?? 0;
  const pageTokensOut =
    data?.runs.reduce((total, run) => total + (run.tokens_out ?? 0), 0) ?? 0;
  const escalations =
    notifications?.notifications.filter(
      (item) => item.kind === "review_escalation" || item.kind === "task_timeout",
    ) ?? [];

  return (
    <section className="card" aria-labelledby="agents-title">
      <div className="card-head">
        <div>
          <h2 id="agents-title">Agents IA</h2>
          <p className="muted">
            Runs ingérés et lancés, coûts, escalades, indépendance et journal en direct.
          </p>
        </div>
        {data ? (
          <span className={`badge ${data.independence.decision_required ? "badge-error" : "badge-done"}`}>
            indépendance {data.independence.degraded_rate_percent ?? "non mesurée"} %
          </span>
        ) : null}
      </div>

      <div className="toolbar" aria-label="Filtres des runs">
        <label className="field" htmlFor="agent-filter">
          <span>Agent</span>
          <input
            id="agent-filter"
            value={agent}
            onChange={(event) => setAgent(event.target.value)}
            placeholder="tous"
          />
        </label>
        <label className="field" htmlFor="role-filter">
          <span>Rôle</span>
          <select id="role-filter" value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="">Tous</option>
            <option value="executor">Exécutant</option>
            <option value="reviewer">Relecteur</option>
          </select>
        </label>
        <label className="field" htmlFor="run-status-filter">
          <span>Statut</span>
          <select
            id="run-status-filter"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">Tous</option>
            {["queued", "running", "done", "failed", "timeout", "cancelled"].map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement des runs…" : ""}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement des runs…</p> : null
      ) : (
        <>
          <div className="summary" aria-label="Indicateurs des runs">
            <div className="metric">
              <span className="metric-value">{data.total}</span>
              <span className="metric-label">Runs</span>
            </div>
            <div className="metric">
              <span className="metric-value">{pageCost.toFixed(2)} €</span>
              <span className="metric-label">Coût de la page</span>
            </div>
            <div className="metric">
              <span className="metric-value">{pageTokensIn + pageTokensOut}</span>
              <span className="metric-label">Tokens de la page</span>
            </div>
            <div className="metric">
              <span className="metric-value">{escalations.length}</span>
              <span className="metric-label">Escalades en attente</span>
            </div>
          </div>

          <div className="banner" aria-labelledby="independence-title">
            <strong id="independence-title">Indépendance des revues</strong>
            <p>{data.independence.detail}</p>
            <p className="muted">
              Fenêtre {data.independence.window_days} jours · seuil{" "}
              {data.independence.threshold_percent} % · {data.independence.total_reviews} revue(s)
              mesurée(s), {data.independence.unmeasured_reviews} non mesurée(s).
            </p>
            {data.independence.decision_required ? (
              <p className="error">
                Décision humaine exigée et auditée :{" "}
                {data.independence_alert?.message ?? "seuil atteint"}.
              </p>
            ) : null}
          </div>

          {data.runs.length === 0 ? (
            <p className="muted">Aucun run ne correspond aux filtres.</p>
          ) : (
            <table className="data-table">
              <caption>Journal des runs</caption>
              <thead>
                <tr>
                  <th scope="col">Tâche</th>
                  <th scope="col">Agent</th>
                  <th scope="col">Rôle</th>
                  <th scope="col">Modèle</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Origine</th>
                  <th scope="col">Durée</th>
                  <th scope="col">Coût</th>
                  <th scope="col">Tokens</th>
                  <th scope="col">Journal</th>
                </tr>
              </thead>
              <tbody>
                {data.runs.map((run) => (
                  <tr key={run.id}>
                    <td>{run.task_key ?? "—"}</td>
                    <td>{run.agent_id ?? "—"}</td>
                    <td>{run.role ?? "—"}</td>
                    <td>{run.model ?? "—"}</td>
                    <td>
                      <span className={`badge badge-${run.status}`}>{run.status}</span>
                    </td>
                    <td>{run.origin}</td>
                    <td>{duration(run)}</td>
                    <td>{cost(run)}</td>
                    <td>
                      {run.tokens_in ?? 0} / {run.tokens_out ?? 0}
                    </td>
                    <td>
                      <button
                        type="button"
                        aria-label={`Ouvrir le journal du run ${run.run_id}`}
                        onClick={() => setSelected(run)}
                      >
                        Journal
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Escalades</h3>
          {escalations.length === 0 ? (
            <p className="muted">Aucune escalade en attente.</p>
          ) : (
            <ul className="compact-list">
              {escalations.map((item) => (
                <li key={item.id}>
                  <span className="badge badge-error">{item.kind}</span>{" "}
                  <strong>{item.message}</strong>
                  <span className="kpi-source"> notifié le {item.created_at}</span>
                </li>
              ))}
            </ul>
          )}

          {selected ? (
            <div className="agent-log">
              <div className="card-head">
                <h3>Run {selected.run_id}</h3>
                <button type="button" onClick={() => setSelected(null)}>
                  Fermer le journal
                </button>
              </div>
              <RunLog runId={selected.run_id} />
            </div>
          ) : null}

          <p className="kpi-source">
            {data.has_more ? "Page partielle ; affiner les filtres pour voir les autres runs." : "Tous les runs filtrés sont affichés."}
          </p>
        </>
      )}
    </section>
  );
}
