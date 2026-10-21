import { useEffect, useState } from "react";
import Markdown from "./Markdown";
import { fetchJson } from "./lib/suivi";
import {
  documentsUrl,
  type DocumentContent,
  type DocumentItem,
  type DocumentsResponse,
} from "./lib/views";

type Props = {
  projectId: number | null;
};

function statusLabel(status: string): string {
  switch (status) {
    case "fresh":
      return "à jour";
    case "stale":
      return "à revoir";
    case "missing":
      return "manquant";
    default:
      return status;
  }
}

export default function Documents({ projectId }: Props) {
  const [data, setData] = useState<DocumentsResponse | null>(null);
  const [selected, setSelected] = useState<DocumentContent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadDocuments(signal?: AbortSignal): Promise<void> {
    if (projectId === null) {
      return;
    }
    const response = await fetchJson<DocumentsResponse>(documentsUrl(projectId));
    if (!signal?.aborted) {
      setData(response);
    }
  }

  useEffect(() => {
    if (projectId === null) {
      setData(null);
      setSelected(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loadDocuments(controller.signal)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Vue Documentation indisponible");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [projectId]);

  async function openDocument(item: DocumentItem): Promise<void> {
    if (projectId === null || !item.exists) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetchJson<DocumentsResponse>(documentsUrl(projectId, item.path));
      setSelected(response.selected ?? null);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Document indisponible");
    } finally {
      setLoading(false);
    }
  }

  async function regenerate(url: string): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      await fetchJson<unknown>(url);
      await loadDocuments();
      setNotice("Document généré à nouveau ; la mention « fichier généré » reste affichée.");
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Régénération impossible");
    } finally {
      setLoading(false);
    }
  }

  if (projectId === null) {
    return null;
  }

  return (
    <section className="card" aria-labelledby="documents-title">
      <div className="card-head">
        <div>
          <h2 id="documents-title">Documentation</h2>
          <p className="muted">
            Fraîcheur, lecteur Markdown sans HTML interprété et régénération des documents générés.
          </p>
        </div>
        {data ? (
          <p className="muted">
            {data.summary.present}/{data.summary.expected} présent(s) · {data.summary.stale} à revoir ·{" "}
            {data.summary.missing} manquant(s)
          </p>
        ) : null}
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement des documents…" : notice}
      </div>

      {data === null ? (
        !error ? <p className="muted">Chargement des documents…</p> : null
      ) : (
        <>
          <table className="data-table">
            <caption>Documents attendus et fraîcheur</caption>
            <thead>
              <tr>
                <th scope="col">Document</th>
                <th scope="col">Chemin</th>
                <th scope="col">Fraîcheur</th>
                <th scope="col">Généré</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.documents.map((item) => (
                <tr key={`${item.key}-${item.path}`}>
                  <td>{item.label}</td>
                  <td>
                    <code>{item.path}</code>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        item.status === "stale" || item.status === "missing"
                          ? "badge-warn"
                          : "badge-done"
                      }`}
                    >
                      {statusLabel(item.status)}
                    </span>
                    {item.age_days !== null ? (
                      <span className="kpi-source"> {item.age_days} jour(s)</span>
                    ) : null}
                  </td>
                  <td>
                    {item.generated ? (
                      <span className="badge badge-warn">fichier généré</span>
                    ) : (
                      <span className="muted">éditable</span>
                    )}
                  </td>
                  <td>
                    {item.exists ? (
                      <div className="toolbar">
                        <button
                          type="button"
                          onClick={() => openDocument(item)}
                          aria-label={`Lire ${item.label} (${item.path})`}
                        >
                          Lire
                        </button>
                        {item.regenerate_url ? (
                          <button
                            type="button"
                            onClick={() => regenerate(item.regenerate_url ?? "")}
                            aria-label={`Régénérer ${item.label}`}
                          >
                            Régénérer
                          </button>
                        ) : null}
                      </div>
                    ) : (
                      <span className="muted">à créer</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {selected ? (
            <article className="document-reader" aria-labelledby="document-reader-title">
              <div className="card-head">
                <div>
                  <p className="eyebrow">{selected.path}</p>
                  <h3 id="document-reader-title">{selected.label}</h3>
                </div>
                <div className="toolbar">
                  {selected.regenerate_url ? (
                    <button type="button" onClick={() => regenerate(selected.regenerate_url ?? "")}>
                      Régénérer
                    </button>
                  ) : null}
                  <button type="button" onClick={() => setSelected(null)}>
                    Fermer
                  </button>
                </div>
              </div>
              {selected.notice ? (
                <p className="banner" role="note">
                  {selected.notice} Utilisez « Régénérer », ne modifiez pas ce fichier à la main.
                </p>
              ) : null}
              {selected.truncated ? (
                <p className="muted">Document tronqué à 200 Ko pour l’affichage.</p>
              ) : null}
              {selected.markdown !== null ? (
                <Markdown markdown={selected.markdown} />
              ) : (
                <pre className="document-text">{selected.text}</pre>
              )}
            </article>
          ) : null}
        </>
      )}
    </section>
  );
}
