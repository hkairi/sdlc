import { useEffect, useState } from "react";
import Features from "./Features";
import Overview from "./Overview";
import {
  fetchJson,
  openSuiviOnce,
  suiviGenerationUrl,
  suiviStatusUrl,
  suiviUrl,
  type Project,
  type SuiviStatus,
} from "./lib/suivi";

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [status, setStatus] = useState<SuiviStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchJson<Project[]>("/api/projects")
      .then((items) => {
        if (cancelled) {
          return;
        }
        setProjects(items);
        setSelectedId(items[0]?.id ?? null);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Erreur de chargement des projets");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedId === null) {
      setStatus(null);
      return;
    }
    let cancelled = false;
    setStatus(null);
    setError(null);
    fetchJson<SuiviStatus>(suiviStatusUrl(selectedId))
      .then((next) => {
        if (!cancelled) {
          setStatus(next);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Suivi indisponible");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  useEffect(() => {
    if (selectedId === null || status === null) {
      return;
    }
    if (openSuiviOnce({ projectId: selectedId, status })) {
      setNotice("Le suivi s'est ouvert dans un nouvel onglet.");
    }
  }, [selectedId, status]);

  useEffect(() => {
    if (selectedId === null || status?.ready) {
      return;
    }
    const timer = window.setInterval(() => {
      fetchJson<SuiviStatus>(suiviStatusUrl(selectedId))
        .then(setStatus)
        .catch(() => {
          // Le prochain passage réessaiera ; l'erreur de chargement initiale reste affichée.
        });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [selectedId, status?.ready]);

  async function generate(): Promise<void> {
    if (selectedId === null) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await fetchJson<unknown>(suiviGenerationUrl(selectedId));
      const next = await fetchJson<SuiviStatus>(suiviStatusUrl(selectedId));
      setStatus(next);
      setNotice("Suivi généré. Le lien persistant est disponible ci-dessous.");
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Échec de génération du suivi");
    } finally {
      setBusy(false);
    }
  }

  const selected = projects.find((project) => project.id === selectedId) ?? null;
  const persistentUrl = selectedId === null ? null : suiviUrl(selectedId);

  return (
    <main className="shell">
      <header>
        <p className="eyebrow">Console SDLC · Suivi</p>
        <h1>Suivi du projet</h1>
        <p className="sub">
          Générez le fichier de suivi, consultez son état et gardez un lien persistant.
          L'ouverture automatique respecte <code>ui.open_suivi_on_ready</code>.
        </p>
      </header>

      <Overview projectId={selectedId} />

      <Features projectId={selectedId} />

      <section className="card" aria-labelledby="suivi-title">
        <div className="card-head">
          <h2 id="suivi-title">Fichier de suivi</h2>
          <div className="toolbar">
            <label className="field" htmlFor="project-select">
              <span>Projet</span>
              <select
                id="project-select"
                value={selectedId ?? ""}
                onChange={(event) => setSelectedId(Number(event.target.value))}
                disabled={projects.length === 0 || busy}
              >
                {projects.length === 0 ? (
                  <option value="">Aucun projet</option>
                ) : (
                  projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))
                )}
              </select>
            </label>
            <button type="button" onClick={generate} disabled={selectedId === null || busy}>
              {busy ? "Génération…" : "Générer le suivi"}
            </button>
            {persistentUrl ? (
              <a className="button-link" href={persistentUrl} target="_blank" rel="noopener noreferrer">
                Ouvrir le suivi
              </a>
            ) : null}
          </div>
        </div>

        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}

        <div className="status-line" role="status" aria-live="polite">
          {notice}
        </div>

        {selected === null ? (
          <p className="muted">Aucun projet disponible. Créez d'abord un projet.</p>
        ) : status === null ? (
          <p className="muted">Chargement de l'état du suivi…</p>
        ) : status.ready ? (
          <>
            <p className="muted">
              Dernière génération : <strong>{status.generated_at ?? "non mesurée"}</strong>
              {status.stale ? <span className="badge badge-warn"> À régénérer</span> : null}
            </p>
            <div className="summary" aria-label="Résumé du suivi">
              <div className="metric">
                <span className="metric-value">{status.summary.features}</span>
                <span className="metric-label">Features</span>
              </div>
              <div className="metric">
                <span className="metric-value">{status.summary.tasks}</span>
                <span className="metric-label">Tâches</span>
              </div>
              <div className="metric">
                <span className="metric-value">{status.summary.done}</span>
                <span className="metric-label">Terminées</span>
              </div>
              <div className="metric">
                <span className="metric-value">{status.summary.progress_percent}%</span>
                <span className="metric-label">Avancement</span>
              </div>
            </div>
            <p className="muted">
              {status.summary.doing} en cours · {status.summary.todo} à faire ·{" "}
              {status.summary.blocked} bloquée(s)
            </p>
            {!status.open_on_ready ? (
              <p className="banner">
                L'ouverture automatique est désactivée (<code>ui.open_suivi_on_ready = false</code>).
                Utilisez le lien persistant « Ouvrir le suivi ».
              </p>
            ) : null}
          </>
        ) : (
          <p className="muted">
            Le suivi n'est pas encore généré. Utilisez « Générer le suivi » ; un lien persistant
            restera disponible.
          </p>
        )}
      </section>
    </main>
  );
}
