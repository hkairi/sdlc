import { useEffect, useState } from "react";
import { fetchJson } from "./lib/suivi";
import {
  decisionsUrl,
  reviewPackagesUrl,
  reviewersUrl,
  type DecisionsResponse,
  type ReviewPackagesResponse,
  type ReviewerResponse,
} from "./lib/review";

type Props = {
  projectId: number | null;
};

export default function Review({ projectId }: Props) {
  const [packages, setPackages] = useState<ReviewPackagesResponse | null>(null);
  const [decisions, setDecisions] = useState<DecisionsResponse | null>(null);
  const [reviewer, setReviewer] = useState<ReviewerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (projectId === null) {
      setPackages(null);
      setDecisions(null);
      setReviewer(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchJson<ReviewPackagesResponse>(reviewPackagesUrl(projectId)),
      fetchJson<DecisionsResponse>(decisionsUrl(projectId)),
      fetchJson<ReviewerResponse>(reviewersUrl(projectId)),
    ])
      .then(([packageData, decisionData, reviewerData]) => {
        if (!cancelled) {
          setPackages(packageData);
          setDecisions(decisionData);
          setReviewer(reviewerData);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Vue Revue indisponible");
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
    <section className="card" aria-labelledby="review-title">
      <div className="card-head">
        <div>
          <h2 id="review-title">Revue indépendante</h2>
          <p className="muted">
            Paquets aveugles, indépendance du relecteur et décisions humaines auditées.
          </p>
        </div>
        {reviewer ? (
          <span
            className={`badge ${
              reviewer.allowed ? "badge-done" : "badge-error"
            }`}
          >
            {reviewer.level}
          </span>
        ) : null}
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement des revues…" : ""}
      </div>

      {packages === null ? (
        !error ? <p className="muted">Chargement des revues…</p> : null
      ) : (
        <>
          <h3>Relecteur proposé</h3>
          {reviewer === null || reviewer.selected === null ? (
            <p className="muted">{reviewer?.reason ?? "Aucun relecteur disponible."}</p>
          ) : (
            <div className="banner">
              <p>
                <strong>{reviewer.selected.label}</strong> — agent{" "}
                {reviewer.selected.agent_id}, modèle {reviewer.selected.model}, famille{" "}
                {reviewer.selected.family}
              </p>
              <p className="muted">
                Niveau {reviewer.level} ·{" "}
                {reviewer.waiver_required ? "dérogation requise" : "revue autorisée"} ·{" "}
                {reviewer.candidates.length} candidat(s)
              </p>
            </div>
          )}

          <h3>Paquets de revue</h3>
          {packages.packages.length === 0 ? (
            <p className="muted">Aucun paquet de revue.</p>
          ) : (
            <table className="data-table">
              <caption>Paquets aveugles et empreintes</caption>
              <thead>
                <tr>
                  <th scope="col">Tâche</th>
                  <th scope="col">Feature</th>
                  <th scope="col">Empreinte</th>
                  <th scope="col">Créé le</th>
                  <th scope="col">Fichier</th>
                </tr>
              </thead>
              <tbody>
                {packages.packages.map((item) => (
                  <tr key={item.id}>
                    <td>{item.task_key}</td>
                    <td>{item.feature_key ?? "—"}</td>
                    <td>
                      <code>{item.fingerprint.slice(0, 16)}…</code>
                    </td>
                    <td>{item.created_at}</td>
                    <td>
                      <code>{item.path}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Décisions humaines</h3>
          {decisions === null || decisions.decisions.length === 0 ? (
            <p className="muted">Aucune décision enregistrée.</p>
          ) : (
            <table className="data-table">
              <caption>Décisions humaines et motifs</caption>
              <thead>
                <tr>
                  <th scope="col">Décision</th>
                  <th scope="col">Sujet</th>
                  <th scope="col">Acteur</th>
                  <th scope="col">Motif</th>
                  <th scope="col">Date</th>
                </tr>
              </thead>
              <tbody>
                {decisions.decisions.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <span
                        className={`badge ${
                          item.decision === "reject" ? "badge-error" : "badge-done"
                        }`}
                      >
                        {item.decision}
                      </span>
                    </td>
                    <td>
                      {item.subject_type} · {item.subject_id}
                    </td>
                    <td>
                      {item.actor_label}
                      {item.unauthenticated ? (
                        <span className="badge badge-warn"> non authentifiée</span>
                      ) : null}
                    </td>
                    <td>{item.reason}</td>
                    <td>{item.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
