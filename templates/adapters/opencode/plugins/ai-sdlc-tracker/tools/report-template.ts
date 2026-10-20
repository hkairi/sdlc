/**
 * Gabarit du rapport de clôture (`sdlc_report`).
 *
 * HTML autonome : styles en ligne dans un `<style>`, aucune ressource externe,
 * aucun script. Le fichier s'ouvre en `file://` et s'imprime comme les suivis.
 */
import type { TaskState } from "../core.ts"

const STATUS_LABELS: Record<string, string> = {
  todo: "À faire",
  doing: "En cours",
  blocked: "Bloqué",
  done: "Terminé",
}

function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
}

export type ReportInput = {
  change: string
  title: string
  project: string
  file: string
  tasksFile: string
  tasks: TaskState[]
  generated: string
}

export function renderReport(input: ReportInput): string {
  const done = input.tasks.filter((t) => t.status === "done").length
  const total = input.tasks.length
  const percent = total === 0 ? 0 : Math.round((done / total) * 100)
  const ecarts = input.tasks.filter((t) => t.status === "blocked" || (t.status === "doing" && t.note === ""))

  const rows = input.tasks
    .map(
      (task) => `      <tr class="st-${esc(task.status)}">
        <td class="id">${esc(task.id)}</td>
        <td>${esc(task.title || "—")}</td>
        <td><span class="pill">${esc(STATUS_LABELS[task.status] ?? task.status)}</span></td>
        <td class="date">${esc(task.updated || "—")}</td>
        <td class="note">${esc(task.note || "—")}</td>
      </tr>`,
    )
    .join("\n")

  const ecartsBlock =
    ecarts.length === 0
      ? `<p class="ok">Aucun écart ouvert : aucune tâche bloquée, aucune tâche en cours sans note.</p>`
      : `<ul class="ecarts">
${ecarts
  .map(
    (task) =>
      `  <li><b>${esc(task.id)}</b> ${esc(task.title || "")} — <i>${esc(STATUS_LABELS[task.status] ?? task.status)}</i> : ${esc(task.note || "aucune note")}</li>`,
  )
  .join("\n")}
</ul>`

  return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rapport de clôture — ${esc(input.change)} · ${esc(input.project)}</title>
<!-- Fichier généré par le plugin ai-sdlc-tracker (outil sdlc_report). Ne pas modifier à la main. -->
<style>
  :root{--bg:#eef1f6;--card:#fff;--ink:#1b2430;--muted:#5c6b7a;--line:#e2e8f0;--brand:#0f4c81;
    --done:#1f9d55;--doing:#2b6cb0;--blocked:#c0392b;--todo:#5c6b7a}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);line-height:1.55;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  .wrap{max-width:1000px;margin:0 auto;padding:28px 22px 60px}
  header{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px 24px;
    box-shadow:0 1px 3px rgba(16,24,40,.08)}
  .eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
  h1{margin:8px 0 6px;font-size:24px;letter-spacing:-.01em}
  .meta{color:var(--muted);font-size:13px}
  .bar{height:8px;border-radius:4px;background:#edf0f5;overflow:hidden;margin:16px 0 6px}
  .bar i{display:block;height:100%;width:${percent}%;background:var(--done)}
  section{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-top:18px;
    padding:18px 20px;box-shadow:0 1px 3px rgba(16,24,40,.06)}
  h2{font-size:16px;margin:0 0 10px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
  th{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
  td.id{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap}
  td.date{white-space:nowrap;color:var(--muted)}
  td.note{color:#3a4553}
  .pill{font-size:11px;font-weight:700;border-radius:999px;padding:1px 8px;border:1px solid;white-space:nowrap}
  tr.st-done .pill{color:#166b3a;background:#e3f6ec;border-color:#bfe6ce}
  tr.st-doing .pill{color:#0f4c81;background:#e8f1fb;border-color:#c7dcf3}
  tr.st-blocked .pill{color:#8f2b21;background:#fdeaea;border-color:#f2c6c1}
  tr.st-todo .pill{color:var(--muted);background:#eef2f8;border-color:var(--line)}
  .ecarts{margin:0;padding-left:20px;font-size:13px}
  .ok{color:#166b3a;margin:0}
  footer{color:var(--muted);font-size:12px;margin-top:18px}
  @media print{body{background:#fff}section,header{box-shadow:none}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">${esc(input.project)} · Rapport de clôture</div>
    <h1>${esc(input.title)}</h1>
    <div class="meta">Change <code>${esc(input.change)}</code> · ${done}/${total} tâches terminées (${percent} %)
      · suivi <code>${esc(input.file)}</code> · tâches <code>${esc(input.tasksFile)}</code>
      · rapport généré le ${esc(input.generated)}</div>
    <div class="bar"><i></i></div>
  </header>

  <section>
    <h2>Écarts ouverts</h2>
    ${ecartsBlock}
  </section>

  <section>
    <h2>Tâches (${total})</h2>
    <table>
      <thead><tr><th>Id</th><th>Tâche</th><th>Statut</th><th>Date</th><th>Note (fait / écart / vérifié)</th></tr></thead>
      <tbody>
${rows}
      </tbody>
    </table>
  </section>

  <footer>Fichier généré par le plugin <code>ai-sdlc-tracker</code> — l'état de référence reste
    <code>${esc(input.file)}</code> et <code>${esc(input.tasksFile)}</code>.</footer>
</div>
</body>
</html>
`
}
