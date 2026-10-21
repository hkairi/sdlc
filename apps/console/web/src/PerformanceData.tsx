import { useEffect, useState } from "react";
import { fetchJson } from "./lib/suivi";
import { qualityUrl, type FindingRef, type QualityView } from "./lib/views";

type Props = {
  projectId: number | null;
};

function valueOrDash(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function FindingList({ findings, empty }: { findings: FindingRef[]; empty: string }) {
  if (findings.length === 0) {
    return <p className="muted">{empty}</p>;
  }
  return (
    <ul className="compact-list">
      {findings.map((finding) => (
        <li key={finding.id}>
          <span className={`badge ${finding.severity === "error" ? "badge-error" : "badge-warn"}`}>
            {finding.severity}
          </span>{" "}
          <strong>{finding.key}</strong>
          <span className="muted"> — {finding.message}</span>
          {finding.file ? (
            <span className="kpi-source">
              {" "}
              {finding.file}
              {finding.line ? `:${finding.line}` : ""}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export default function PerformanceData({ projectId }: Props) {
  const [data, setData] = useState<QualityView | null>(null);
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
    fetchJson<QualityView>(qualityUrl(projectId))
      .then((next) => {
        if (!cancelled) {
          setData(next);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            cause instanceof Error ? cause.message : "Vue Performance & données indisponible",
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

  return (
    <section className="card" aria-labelledby="quality-title">
      <div className="card-head">
        <div>
          <h2 id="quality-title">Performance & données</h2>
          <p className="muted">
            Budgets observés, signaux statiques, PII, migrations et sauvegarde vérifiée.
          </p>
        </div>
        {data ? (
          <div className="toolbar">
            <span className={`badge ${data.performance.blocks ? "badge-error" : "badge-done"}`}>
              perf {data.performance.verdict}
            </span>
            <span className={`badge ${data.data.blocks ? "badge-error" : "badge-done"}`}>
              data {data.data.verdict}
            </span>
          </div>
        ) : null}
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement de la performance et des données…" : ""}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement de la performance et des données…</p> : null
      ) : (
        <>
          <h3>Performance observée</h3>
          <div className="summary" aria-label="Budgets de performance">
            {Object.entries(data.performance.budgets).map(([key, value]) => (
              <div className="metric" key={key}>
                <span className="metric-value">{value ?? "—"}</span>
                <span className="metric-label">{key}</span>
              </div>
            ))}
          </div>

          {data.performance.cases.length === 0 ? (
            <p className="muted">Aucun cas observé dans les preuves de performance.</p>
          ) : (
            <table className="data-table">
              <caption>Cas de performance observés</caption>
              <thead>
                <tr>
                  <th scope="col">Cas</th>
                  <th scope="col">p50</th>
                  <th scope="col">p95</th>
                  <th scope="col">p99</th>
                  <th scope="col">Budget</th>
                  <th scope="col">Commit</th>
                </tr>
              </thead>
              <tbody>
                {data.performance.cases.map((item, index) => (
                  <tr key={`${String(item.case ?? item.name ?? "cas")}-${index}`}>
                    <td>{valueOrDash(item.case ?? item.name)}</td>
                    <td>{valueOrDash(item.p50_ms)}</td>
                    <td>{valueOrDash(item.p95_ms)}</td>
                    <td>{valueOrDash(item.p99_ms)}</td>
                    <td>{valueOrDash(item.budget_ms)}</td>
                    <td>{valueOrDash(item.commit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Signaux statiques</h3>
          <FindingList
            findings={data.performance.signals}
            empty="Aucun signal statique."
          />

          <h3>Données et PII</h3>
          <div className="summary" aria-label="Indicateurs de données">
            <div className="metric">
              <span className="metric-value">{data.data.pii.length}</span>
              <span className="metric-label">PII détectées</span>
            </div>
            <div className="metric">
              <span className="metric-value">{data.data.migrations.length}</span>
              <span className="metric-label">Migrations à risque</span>
            </div>
            <div className="metric">
              <span className="metric-value">
                {data.data.backup.age_hours === null ? "non mesuré" : `${data.data.backup.age_hours} h`}
              </span>
              <span className="metric-label">Âge sauvegarde</span>
            </div>
          </div>

          <div className="view-grid">
            <div>
              <h4>PII dans les logs</h4>
              <FindingList findings={data.data.pii} empty="Aucune PII détectée." />
              <h4>Migrations</h4>
              <FindingList
                findings={data.data.migrations}
                empty="Aucune migration destructive détectée."
              />
            </div>
            <div>
              <h4>Sauvegarde et schéma</h4>
              <p>
                <strong>Sauvegarde :</strong>{" "}
                {data.data.backup.status === "measured"
                  ? `vérifiée=${valueOrDash(data.data.backup.verified)}, restauration testée=${valueOrDash(data.data.backup.restore_tested)}`
                  : "non mesurée"}
              </p>
              <p className="muted">{data.data.backup.reason ?? data.data.backup.source}</p>
              <p>
                <strong>Rétention :</strong>{" "}
                {data.data.retention_days === null
                  ? "non définie"
                  : `${data.data.retention_days} jour(s)`}
              </p>
              <p>
                <strong>Schéma :</strong>{" "}
                {data.data.schema.status === "measured"
                  ? `${data.data.schema.current ?? "aucune"} / ${data.data.schema.head ?? "aucune"}`
                  : "non mesuré"}
                {data.data.schema.up_to_date === false ? (
                  <span className="badge badge-warn"> migration requise</span>
                ) : null}
              </p>
            </div>
          </div>
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
