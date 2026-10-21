import { useEffect, useState } from "react";
import { fetchJson } from "./lib/suivi";
import {
  ownershipUrl,
  teamUrl,
  type OwnershipResponse,
  type TeamResponse,
} from "./lib/team";

type Props = {
  projectId: number | null;
};

export default function Team({ projectId }: Props) {
  const [data, setData] = useState<TeamResponse | null>(null);
  const [ownership, setOwnership] = useState<OwnershipResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (projectId === null) {
      setData(null);
      setOwnership(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchJson<TeamResponse>(teamUrl(projectId)),
      fetchJson<OwnershipResponse>(ownershipUrl(projectId)),
    ])
      .then(([team, owner]) => {
        if (!cancelled) {
          setData(team);
          setOwnership(owner);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Vue Équipe indisponible");
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
    <section className="card" aria-labelledby="team-title">
      <div className="card-head">
        <div>
          <h2 id="team-title">Équipe</h2>
          <p className="muted">
            Métriques par personne et dépôt, bus factor, propriété et chaîne de validation.
          </p>
        </div>
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement de l'équipe…" : ""}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement de l'équipe…</p> : null
      ) : (
        <>
          <div className="summary" aria-label="Totaux d'équipe">
            <div className="metric">
              <span className="metric-value">{data.totals.commits}</span>
              <span className="metric-label">Commits</span>
            </div>
            <div className="metric">
              <span className="metric-value">{data.totals.merged_requests}</span>
              <span className="metric-label">MR fusionnées</span>
            </div>
            <div className="metric">
              <span className="metric-value">{data.totals.reviews}</span>
              <span className="metric-label">Revues</span>
            </div>
            <div className="metric">
              <span className="metric-value">
                {data.totals.ai_percent === null
                  ? "non mesuré"
                  : `${data.totals.ai_percent} %`}
              </span>
              <span className="metric-label">Commits assistés IA</span>
            </div>
          </div>

          <h3>Chaîne de validation</h3>
          <p>
            {data.validation.status === "measured"
              ? `${data.validation.total} MR · relecture agent ${data.validation.agent_review_rate ?? "non mesurée"} % · approbation humaine ${data.validation.human_approval_rate ?? "non mesurée"} % · complète ${data.validation.complete_rate ?? "non mesurée"} %`
              : "Non mesurée : aucune MR."}
          </p>

          <h3>Dépôts</h3>
          {data.repositories.length === 0 ? (
            <p className="muted">Aucun dépôt actif.</p>
          ) : (
            <table className="data-table">
              <caption>Métriques par dépôt</caption>
              <thead>
                <tr>
                  <th scope="col">Dépôt</th>
                  <th scope="col">Commits</th>
                  <th scope="col">MR</th>
                  <th scope="col">Revues</th>
                  <th scope="col">Approbations</th>
                  <th scope="col">Personnes</th>
                </tr>
              </thead>
              <tbody>
                {data.repositories.map((repository) => (
                  <tr key={repository.repository_id}>
                    <td>{repository.repository_name}</td>
                    <td>{repository.commits}</td>
                    <td>{repository.merged_requests}</td>
                    <td>{repository.reviews}</td>
                    <td>{repository.approvals}</td>
                    <td>{repository.persons}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Personnes</h3>
          {data.persons.length === 0 ? (
            <p className="muted">Aucune personne mesurée.</p>
          ) : (
            <table className="data-table">
              <caption>Contribution par personne canonique</caption>
              <thead>
                <tr>
                  <th scope="col">Personne</th>
                  <th scope="col">Rôle</th>
                  <th scope="col">Commits</th>
                  <th scope="col">MR</th>
                  <th scope="col">Revues</th>
                  <th scope="col">Approbations</th>
                </tr>
              </thead>
              <tbody>
                {data.persons.map((person) => (
                  <tr key={person.person.id}>
                    <td>{person.person.display_name}</td>
                    <td>{person.person.role ?? "—"}</td>
                    <td>{person.commits}</td>
                    <td>{person.merged_requests}</td>
                    <td>{person.reviews}</td>
                    <td>{person.approvals}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Bus factor et propriété</h3>
          {ownership === null || ownership.zones.length === 0 ? (
            <p className="muted">Aucune zone CODEOWNERS mesurée.</p>
          ) : (
            <table className="data-table">
              <caption>Bus factor par zone</caption>
              <thead>
                <tr>
                  <th scope="col">Zone</th>
                  <th scope="col">Dépôt</th>
                  <th scope="col">Bus factor</th>
                  <th scope="col">Propriétaire principal</th>
                  <th scope="col">Statut</th>
                </tr>
              </thead>
              <tbody>
                {ownership.zones.map((zone) => (
                  <tr key={`${zone.repository_name}-${zone.zone}`}>
                    <td>
                      <code>{zone.zone}</code>
                    </td>
                    <td>{zone.repository_name}</td>
                    <td>
                      <span className={`badge ${zone.risk ? "badge-error" : "badge-done"}`}>
                        {zone.bus_factor}
                      </span>
                    </td>
                    <td>{zone.primary_owner?.name ?? "non mesuré"}</td>
                    <td>{zone.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {ownership !== null && ownership.alerts.length > 0 ? (
            <div className="banner" role="alert">
              <strong>Alertes de bus factor</strong>
              <ul>
                {ownership.alerts.map((alert) => (
                  <li key={`${alert.zone}-${alert.message}`}>{alert.message}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
