import { useEffect, useState } from "react";
import { fetchJson } from "./lib/suivi";
import {
  processFlowUrl,
  processUrl,
  type ProcessFlowResponse,
  type ProcessResponse,
} from "./lib/process";

type Props = {
  projectId: number | null;
};

function confidence(value: number | null): string {
  return value === null ? "non mesurée" : `${Math.round(value * 100)} %`;
}

function stepClass(status: string): string {
  if (status === "fail") {
    return "badge badge-error";
  }
  if (status === "warn" || status === "not_measured") {
    return "badge badge-warn";
  }
  if (status === "pass" || status === "done") {
    return "badge badge-done";
  }
  return "badge";
}

export default function Process({ projectId }: Props) {
  const [data, setData] = useState<ProcessResponse | null>(null);
  const [flow, setFlow] = useState<ProcessFlowResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (projectId === null) {
      setData(null);
      setFlow(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchJson<ProcessResponse>(processUrl(projectId)),
      fetchJson<ProcessFlowResponse>(processFlowUrl(projectId)),
    ])
      .then(([process, processFlow]) => {
        if (!cancelled) {
          setData(process);
          setFlow(processFlow);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Vue Processus indisponible");
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
    <section className="card" aria-labelledby="process-title">
      <div className="card-head">
        <div>
          <h2 id="process-title">Processus</h2>
          <p className="muted">
            Profil détecté par dépôt, confiance, divergences et flux avec gates.
          </p>
        </div>
        {data ? (
          <span className={`badge ${data.divergent ? "badge-warn" : "badge-done"}`}>
            {data.divergent ? "divergent" : "aligné"}
          </span>
        ) : null}
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement du processus…" : ""}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement du processus…</p> : null
      ) : (
        <>
          <p>
            <strong>Profil projet :</strong>{" "}
            {data.project_profile
              ? `${data.project_profile.label} (${data.project_profile.source})`
              : "non mesuré"}
          </p>
          {data.profiles.length > 0 ? (
            <p className="muted">
              Profils :{" "}
              {data.profiles.map((profile) => `${profile.label} (${profile.count})`).join(" · ")}
            </p>
          ) : null}

          <h3>Dépôts</h3>
          {data.repositories.length === 0 ? (
            <p className="muted">Aucun dépôt actif.</p>
          ) : (
            <table className="data-table">
              <caption>Profil de processus par dépôt</caption>
              <thead>
                <tr>
                  <th scope="col">Dépôt</th>
                  <th scope="col">Profil</th>
                  <th scope="col">Confiance</th>
                  <th scope="col">Source</th>
                  <th scope="col">Surcharge</th>
                </tr>
              </thead>
              <tbody>
                {data.repositories.map((repository) => (
                  <tr key={repository.repository_id}>
                    <td>{repository.repository_name}</td>
                    <td>{repository.label}</td>
                    <td>{confidence(repository.confidence)}</td>
                    <td>{repository.source}</td>
                    <td>{repository.override?.reason ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {data.divergences.length > 0 ? (
            <div className="banner" role="alert">
              <strong>Divergences de processus</strong>
              <ul>
                {data.divergences.map((divergence) => (
                  <li key={divergence.key}>
                    {divergence.label} — {divergence.repositories.join(", ")}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <h3>Flux et gates</h3>
          {flow === null ? (
            <p className="muted">Flux non disponible.</p>
          ) : (
            <div className="view-grid">
              {flow.flows.map((current) => (
                <div key={current.id}>
                  <h4>{current.label}</h4>
                  <ol className="compact-list">
                    {current.steps.map((step) => (
                      <li key={`${current.id}-${step.id}-${step.label}`}>
                        <span className={stepClass(step.status)}>{step.status}</span>{" "}
                        {step.label}
                        {step.evidence ? (
                          <span className="kpi-source"> preuve : {step.evidence}</span>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
