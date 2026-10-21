import { useEffect, useState } from "react";
import { fetchJson } from "./lib/suivi";
import { configurationUrl, type ConfigurationView } from "./lib/views";

type Props = {
  projectId: number | null;
};

function displayValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function originClass(origin: string): string {
  if (origin === "mesurée") {
    return "badge badge-done";
  }
  if (origin === "détectée") {
    return "badge badge-doing";
  }
  return "badge";
}

export default function Configuration({ projectId }: Props) {
  const [data, setData] = useState<ConfigurationView | null>(null);
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
    fetchJson<ConfigurationView>(configurationUrl(projectId))
      .then((next) => {
        if (!cancelled) {
          setData(next);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Vue Configuration indisponible");
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
    <section className="card" aria-labelledby="configuration-title">
      <div className="card-head">
        <div>
          <h2 id="configuration-title">Configuration</h2>
          <p className="muted">
            Configuration effective, validation JSON Schema et origine de chaque donnée.
          </p>
        </div>
        {data ? (
          <span className={`badge ${data.validation.valid ? "badge-done" : "badge-error"}`}>
            {data.validation.valid ? "valide" : "invalide"}
          </span>
        ) : null}
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement de la configuration…" : ""}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement de la configuration…</p> : null
      ) : (
        <>
          <p>
            <strong>Fichier :</strong> <code>{data.config_file.path}</code>{" "}
            <span className={`badge ${data.config_file.exists ? "badge-done" : "badge-warn"}`}>
              {data.config_file.exists ? "présent" : "absent"}
            </span>
          </p>
          <p className="muted">{data.notice}</p>

          <h3>Validation</h3>
          {data.validation.valid ? (
            <p className="badge badge-done">
              Valide contre {data.validation.schema_title ?? data.validation.schema_id}
            </p>
          ) : (
            <div className="error" role="alert">
              <p>Configuration invalide :</p>
              <ul>
                {data.validation.errors.map((item) => (
                  <li key={`${item.path}-${item.message}`}>
                    <code>{item.path}</code> — {item.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <h3>Origine des données</h3>
          <table className="data-table">
            <caption>Données déclarées, détectées et mesurées</caption>
            <thead>
              <tr>
                <th scope="col">Clé</th>
                <th scope="col">Valeur</th>
                <th scope="col">Origine</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {data.origins.map((row) => (
                <tr key={`${row.origin}-${row.key}`}>
                  <td>
                    <code>{row.key}</code>
                  </td>
                  <td>{displayValue(row.value)}</td>
                  <td>
                    <span className={originClass(row.origin)}>{row.origin}</span>
                  </td>
                  <td className="muted">{row.source}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Configuration effective</h3>
          <pre className="document-text">{JSON.stringify(data.effective, null, 2)}</pre>
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
