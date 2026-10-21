import { useEffect, useState } from "react";
import { fetchJson } from "./lib/suivi";
import {
  findingsUrl,
  gatesUrl,
  type FindingsResponse,
  type GatesResponse,
} from "./lib/gates";

type Props = {
  projectId: number | null;
};

function verdictClass(verdict: string): string {
  if (["fail", "not_run"].includes(verdict)) {
    return "badge badge-error";
  }
  if (verdict === "warn") {
    return "badge badge-warn";
  }
  return "badge badge-done";
}

export default function Gates({ projectId }: Props) {
  const [data, setData] = useState<GatesResponse | null>(null);
  const [findings, setFindings] = useState<FindingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (projectId === null) {
      setData(null);
      setFindings(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchJson<GatesResponse>(gatesUrl(projectId)),
      fetchJson<FindingsResponse>(findingsUrl(projectId)),
    ])
      .then(([gates, recent]) => {
        if (!cancelled) {
          setData(gates);
          setFindings(recent);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Vue Gates indisponible");
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

  const failing = data?.gates.filter((gate) => gate.blocks).length ?? 0;

  return (
    <section className="card" aria-labelledby="gates-title">
      <div className="card-head">
        <div>
          <h2 id="gates-title">Gates & qualité</h2>
          <p className="muted">
            Verdicts fondés sur des preuves, contrôles, dérogations et findings récents.
          </p>
        </div>
        {data ? (
          <span className={`badge ${failing > 0 ? "badge-error" : "badge-done"}`}>
            {failing} gate(s) bloquant(s)
          </span>
        ) : null}
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement des gates…" : ""}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement des gates…</p> : null
      ) : (
        <>
          {data.gates.length === 0 ? (
            <p className="muted">Aucun gate exécuté. Les verdicts restent « non mesurés ».</p>
          ) : (
            <table className="data-table">
              <caption>Dernier verdict par gate</caption>
              <thead>
                <tr>
                  <th scope="col">Gate</th>
                  <th scope="col">Verdict</th>
                  <th scope="col">Bloquant</th>
                  <th scope="col">Findings</th>
                  <th scope="col">Preuve</th>
                </tr>
              </thead>
              <tbody>
                {data.gates.map((gate) => (
                  <tr key={gate.gate_key}>
                    <td>
                      <strong>{gate.name}</strong>
                      {gate.recalculate_required ? (
                        <span className="badge badge-warn"> recalcul requis</span>
                      ) : null}
                    </td>
                    <td>
                      <span className={verdictClass(gate.verdict)}>{gate.verdict}</span>
                    </td>
                    <td>{gate.blocks ? "oui" : "non"}</td>
                    <td>{gate.findings_count}</td>
                    <td>
                      <code>{gate.report_path}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Dérogations actives</h3>
          {data.gates.flatMap((gate) => gate.waivers).length === 0 ? (
            <p className="muted">Aucune dérogation.</p>
          ) : (
            <ul className="compact-list">
              {data.gates
                .flatMap((gate) => gate.waivers)
                .map((waiver) => (
                  <li key={waiver.id}>
                    <span className={`badge badge-${waiver.active ? "warn" : "error"}`}>
                      {waiver.status}
                    </span>{" "}
                    <strong>{waiver.gate_key}</strong>{" "}
                    <span className="muted">— {waiver.reason}</span>
                  </li>
                ))}
            </ul>
          )}

          <h3>Findings récents</h3>
          {findings === null || findings.findings.length === 0 ? (
            <p className="muted">Aucun finding.</p>
          ) : (
            <table className="data-table">
              <caption>Findings récents, toutes preuves</caption>
              <thead>
                <tr>
                  <th scope="col">Sévérité</th>
                  <th scope="col">Finding</th>
                  <th scope="col">Emplacement</th>
                </tr>
              </thead>
              <tbody>
                {findings.findings.map((finding) => (
                  <tr key={finding.id}>
                    <td>
                      <span
                        className={`badge ${
                          finding.severity === "error" ? "badge-error" : "badge-warn"
                        }`}
                      >
                        {finding.severity}
                      </span>
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
