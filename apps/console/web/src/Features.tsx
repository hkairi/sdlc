import { useEffect, useState } from "react";
import {
  featuresUrl,
  taskDetailUrl,
  type FeatureItem,
  type FeaturesResponse,
  type TaskDetail,
} from "./lib/features";
import { fetchJson } from "./lib/suivi";

type Props = {
  projectId: number | null;
};

function phaseStatusLabel(status: string): string {
  switch (status) {
    case "done":
      return "Terminée";
    case "doing":
      return "En cours";
    case "failed":
      return "En échec";
    case "todo":
      return "À faire";
    default:
      return "Non mesurée";
  }
}

function initialFilter(name: string): string {
  return new URLSearchParams(window.location.search).get(name) ?? "";
}

function updateQuery(phase: string, gate: string): void {
  const params = new URLSearchParams(window.location.search);
  if (phase) {
    params.set("phase", phase);
  } else {
    params.delete("phase");
  }
  if (gate) {
    params.set("gate", gate);
  } else {
    params.delete("gate");
  }
  const query = params.toString();
  const next = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
  window.history.replaceState(null, "", next);
}

export default function Features({ projectId }: Props) {
  const [phase, setPhase] = useState(() => initialFilter("phase"));
  const [gate, setGate] = useState(() => initialFilter("gate"));
  const [data, setData] = useState<FeaturesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);

  useEffect(() => {
    updateQuery(phase, gate);
  }, [phase, gate]);

  useEffect(() => {
    if (projectId === null) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchJson<FeaturesResponse>(featuresUrl(projectId, phase, gate))
      .then((next) => {
        if (!cancelled) {
          setData(next);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            cause instanceof Error ? cause.message : "Features indisponibles",
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
  }, [projectId, phase, gate]);

  async function openTask(taskId: number): Promise<void> {
    if (projectId === null) {
      return;
    }
    setTaskLoading(true);
    setTaskError(null);
    try {
      const detail = await fetchJson<TaskDetail>(taskDetailUrl(projectId, taskId));
      setTask(detail);
    } catch (cause: unknown) {
      setTaskError(
        cause instanceof Error ? cause.message : "Détail de tâche indisponible",
      );
    } finally {
      setTaskLoading(false);
    }
  }

  if (projectId === null) {
    return null;
  }

  return (
    <section className="card" aria-labelledby="features-title">
      <div className="card-head">
        <div>
          <h2 id="features-title">Features & tâches</h2>
          <p className="muted">
            Filtrez par phase et par gate. Les filtres restent dans l'URL.
          </p>
        </div>
        <div className="toolbar">
          <label className="field" htmlFor="phase-filter">
            <span>Phase</span>
            <select
              id="phase-filter"
              value={phase}
              onChange={(event) => setPhase(event.target.value)}
            >
              <option value="">Toutes</option>
              {(data?.available_phases ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field" htmlFor="gate-filter">
            <span>Gate</span>
            <select
              id="gate-filter"
              value={gate}
              onChange={(event) => setGate(event.target.value)}
            >
              <option value="">Tous</option>
              {(data?.available_gates ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="status-line" aria-live="polite">
        {loading ? "Chargement des features…" : ""}
        {taskLoading ? "Chargement de la tâche…" : ""}
      </div>

      {taskError ? (
        <p className="error" role="alert">
          {taskError}
        </p>
      ) : null}

      {data ? (
        <>
          {data.inconsistencies.length > 0 ? (
            <div className="banner" aria-labelledby="inconsistencies-title">
              <strong id="inconsistencies-title">
                {data.inconsistencies.length} incohérence(s) tasks.md ↔ state.json
              </strong>
              <ul>
                {data.inconsistencies.map((item) => (
                  <li key={item.id}>
                    {item.feature_key} · {item.task_key} — {item.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {data.features.length === 0 ? (
            <p className="muted">Aucune feature ne correspond aux filtres.</p>
          ) : (
            <ul className="feature-list">
              {data.features.map((feature) => (
                <FeatureCard
                  feature={feature}
                  key={feature.id}
                  onOpenTask={openTask}
                />
              ))}
            </ul>
          )}
        </>
      ) : !error ? (
        <p className="muted">Chargement des features…</p>
      ) : null}

      {task ? (
        <aside className="task-detail" aria-labelledby="task-detail-title">
          <div className="card-head">
            <div>
              <p className="eyebrow">
                {task.feature.key} · {task.feature.phase.name}
              </p>
              <h3 id="task-detail-title">
                {task.key} {task.title}
              </h3>
            </div>
            <button type="button" onClick={() => setTask(null)}>
              Fermer
            </button>
          </div>
          <p>
            <strong>Statut :</strong> {task.status_label} ·{" "}
            <strong>Lot :</strong> {task.lot ?? "—"}
          </p>
          <p>
            <strong>Exécutant :</strong> {task.executor ?? "—"} ·{" "}
            <strong>Relecteur :</strong> {task.reviewer ?? "—"}
          </p>
          <p>
            <strong>Fichiers :</strong>{" "}
            {task.files.length > 0 ? task.files.join(", ") : "aucun fichier déclaré"}
          </p>
          <p>
            <strong>Critères d'acceptation :</strong>{" "}
            {task.acceptance ?? "non renseignés"}
          </p>
          <p>
            <strong>Note :</strong> {task.note ?? "aucune note"}
          </p>
          {task.report_available ? (
            <p>
              <a
                href={task.report_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Ouvrir le rapport de fin de tâche
              </a>
            </p>
          ) : (
            <p className="muted">Rapport de fin de tâche non disponible.</p>
          )}
          <p className="kpi-source">Source : {task.source}</p>
        </aside>
      ) : null}
    </section>
  );
}

function FeatureCard({
  feature,
  onOpenTask,
}: {
  feature: FeatureItem;
  onOpenTask: (taskId: number) => void;
}) {
  return (
    <li className="feature-card">
      <div className="feature-head">
        <div>
          <p className="eyebrow">
            {feature.phase.name} · {feature.key}
          </p>
          <h3>{feature.name}</h3>
        </div>
        <div className="feature-badges">
          <span className={`badge badge-${feature.status}`}>
            {feature.status_label}
          </span>
          <span className={`badge badge-${feature.phase.status}`}>
            Phase : {phaseStatusLabel(feature.phase.status)}
          </span>
        </div>
      </div>
      {feature.objective ? <p className="muted">{feature.objective}</p> : null}
      <p className="meta">
        Spec : {feature.spec_path ?? "non renseignée"} · Tâches :{" "}
        {feature.tasks_file ?? "non renseignées"}
        {feature.change ? ` · Change : ${feature.change}` : ""}
      </p>
      {Object.keys(feature.sources ?? {}).length > 0 ? (
        <p className="meta">
          Sources :{" "}
          {Object.entries(feature.sources ?? {})
            .map(([key, value]) => `${key} (${value})`)
            .join(", ")}
        </p>
      ) : null}
      <p className="meta">
        Couverture : {feature.coverage.label} ({feature.coverage.source}) · Gate :{" "}
        {feature.gate.label} ({feature.gate.source})
      </p>
      <p className="meta">
        Exécutants : {feature.executors.join(", ") || "—"} · Relecteurs :{" "}
        {feature.reviewers.join(", ") || "—"} · Dépôts :{" "}
        {feature.repositories.map((repository) => repository.name).join(", ") || "—"}
      </p>
      <p className="meta">
        {feature.task_summary.done} / {feature.task_summary.total} tâches terminées ·{" "}
        {feature.task_summary.progress_percent}% · {feature.task_summary.blocked}{" "}
        bloquée(s)
      </p>
      {feature.inconsistencies.length > 0 ? (
        <p className="badge badge-error">
          {feature.inconsistencies.length} incohérence(s)
        </p>
      ) : null}
      <table>
        <caption>Tâches de la feature {feature.name}</caption>
        <thead>
          <tr>
            <th scope="col">Tâche</th>
            <th scope="col">Statut</th>
            <th scope="col">Exécutant</th>
            <th scope="col">Relecteur</th>
          </tr>
        </thead>
        <tbody>
          {feature.tasks.length === 0 ? (
            <tr>
              <td colSpan={4}>Aucune tâche.</td>
            </tr>
          ) : (
            feature.tasks.map((task) => (
              <tr key={task.id}>
                <td>
                  <button
                    type="button"
                    className="task-link"
                    onClick={() => onOpenTask(task.id)}
                  >
                    {task.key} {task.title}
                  </button>
                </td>
                <td>
                  <span className={`badge badge-${task.status}`}>
                    {task.status_label}
                  </span>
                </td>
                <td>{task.executor ?? "—"}</td>
                <td>{task.reviewer ?? "—"}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </li>
  );
}
