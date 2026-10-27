/**
 * Gabarit du rapport de clôture (`sdlc_report`).
 *
 * HTML autonome : styles en ligne dans un `<style>`, aucune ressource externe,
 * un seul script (bascule de thème clair/sombre). Le fichier s'ouvre en `file://`
 * et s'imprime comme les suivis.
 * Charte identique aux suivis (`mockup-framework.html`) : bleu marine #0f4c81,
 * cartes, badges de statut, thème clair/sombre via `prefers-color-scheme`.
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
  const blocked = input.tasks.filter((t) => t.status === "blocked").length
  const doing = input.tasks.filter((t) => t.status === "doing").length
  const todo = input.tasks.filter((t) => t.status === "todo").length
  const ecarts = input.tasks.filter((t) => t.status === "blocked" || (t.status === "doing" && t.note === ""))

  const rows = input.tasks
    .map(
      (task) => `      <tr class="st-${esc(task.status)}">
        <td class="id">${esc(task.id)}</td>
        <td>${esc(task.title || "—")}</td>
        <td><span class="badge ${esc(task.status)}">${esc(STATUS_LABELS[task.status] ?? task.status)}</span></td>
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
<meta name="color-scheme" content="light dark">
<style>
  :root{
    color-scheme: light;
    --bg:#eef1f6; --panel:#fff; --ink:#1b2430; --muted:#5c6b7a; --line:#e2e8f0; --line2:#eef2f8; --soft:#f7f9fc;
    --brand:#0f4c81; --brand2:#1379b0; --brandbg:#e8f1fb; --brandline:#c7dcf3;
    --done:#1f9d55; --donebg:#e6f6ec; --doing:#2b6cb0; --doingbg:#e6effa;
    --warn:#b7791f; --warnbg:#fdf3e0; --bad:#c0392b; --badbg:#fdecea;
    --review:#6b4fbb; --reviewbg:#f0ecfb; --todo:#5c6b7a; --turn:#eef2f8;
    --nav:#0f4c81; --nav2:#0a2c4d;
    --shadow:0 1px 3px rgba(16,24,40,.08),0 8px 24px rgba(16,24,40,.05);
    --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  }
  @media (prefers-color-scheme: dark){
    :root:where(:not([data-theme="light"])){
      color-scheme: dark;
      --bg:#121417; --panel:#1a1d21; --ink:#e8ebef; --muted:#a3adb8; --line:#2c3138; --line2:#24282e; --soft:#20242a;
      --brand:#3b82c4; --brand2:#4b9ad6; --brandbg:#1d2a38; --brandline:#2f4a63;
      --done:#3cc479; --donebg:#16281e; --doing:#5b9be0; --doingbg:#182636;
      --warn:#e0b25c; --warnbg:#2b2414; --bad:#e66767; --badbg:#2e1b19;
      --review:#a48be8; --reviewbg:#241d3a; --todo:#a3adb8; --turn:#24282e;
      --nav:#12293f; --nav2:#0d1a26;
      --shadow:0 1px 3px rgba(0,0,0,.4);
    }
  }
  :root[data-theme="dark"]{
    color-scheme: dark;
    --bg:#121417; --panel:#1a1d21; --ink:#e8ebef; --muted:#a3adb8; --line:#2c3138; --line2:#24282e; --soft:#20242a;
    --brand:#3b82c4; --brand2:#4b9ad6; --brandbg:#1d2a38; --brandline:#2f4a63;
    --done:#3cc479; --donebg:#16281e; --doing:#5b9be0; --doingbg:#182636;
    --warn:#e0b25c; --warnbg:#2b2414; --bad:#e66767; --badbg:#2e1b19;
    --review:#a48be8; --reviewbg:#241d3a; --todo:#a3adb8; --turn:#24282e;
    --nav:#12293f; --nav2:#0d1a26;
    --shadow:0 1px 3px rgba(0,0,0,.4);
  }
  :root[data-theme="light"]{color-scheme: light}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);line-height:1.55;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased}
  code{font-family:var(--mono);font-size:.9em;background:var(--soft);border:1px solid var(--line2);padding:0 5px;border-radius:5px}
  .wrap{max-width:1000px;margin:0 auto;padding:28px 22px 60px}

  header.brand{background:linear-gradient(135deg,var(--nav),var(--nav2));color:#fff;border-radius:16px;padding:24px 26px;
    box-shadow:var(--shadow);position:relative}
  .theme{position:absolute;top:14px;right:14px;width:34px;height:34px;border-radius:9px;
    border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.12);color:#fff;
    display:grid;place-items:center;cursor:pointer}
  .theme:hover{background:rgba(255,255,255,.22)}
  .theme svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
  .eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#9dc2e4;font-weight:800}
  h1{margin:8px 0 10px;font-size:24px;letter-spacing:-.01em}
  .meta{color:#dce9f7;font-size:13px}
  .meta code{background:rgba(255,255,255,.14);border:0;color:#fff}

  .kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0 0}
  .kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px 16px;box-shadow:var(--shadow)}
  .kpi .l{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:800}
  .kpi .v{font-size:23px;font-weight:800;line-height:1.15;margin:4px 0 0;font-variant-numeric:tabular-nums}

  .bar{height:8px;border-radius:999px;background:var(--line2);overflow:hidden;margin:16px 0 2px}
  .bar i{display:block;height:100%;width:${percent}%;background:var(--done);border-radius:999px}
  .bar-cap{font-size:11.5px;color:var(--muted)}

  section{background:var(--panel);border:1px solid var(--line);border-radius:14px;margin-top:16px;
    padding:18px 20px;box-shadow:var(--shadow)}
  h2{font-size:15.5px;margin:0 0 10px}
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line2);vertical-align:top}
  thead th{background:var(--soft);font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
    border-bottom:1px solid var(--line);white-space:nowrap}
  tbody tr:last-child td{border-bottom:0}
  tbody tr:hover td{background:var(--soft)}
  td.id{font-family:var(--mono);font-size:12.5px;white-space:nowrap}
  td.date{white-space:nowrap;color:var(--muted)}
  td.note{color:var(--muted)}

  .badge{display:inline-block;font-size:10.5px;font-weight:800;border-radius:999px;padding:2px 9px;border:1px solid;white-space:nowrap}
  .badge.done{background:var(--donebg);color:var(--done);border-color:var(--done)}
  .badge.doing{background:var(--doingbg);color:var(--doing);border-color:var(--doing)}
  .badge.blocked{background:var(--badbg);color:var(--bad);border-color:var(--bad)}
  .badge.todo{background:var(--turn);color:var(--todo);border-color:var(--line)}

  .ecarts{margin:0;padding-left:20px;font-size:13px}
  .ok{color:var(--done);margin:0;font-weight:600}
  footer{color:var(--muted);font-size:12px;margin-top:18px}
  @media(max-width:640px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media print{body{background:#fff}section,header,.kpi{box-shadow:none}}
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
  <symbol id="i-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></symbol>
  <symbol id="i-moon" viewBox="0 0 24 24"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z"/></symbol>
</svg>
<div class="wrap">
  <header class="brand">
    <button class="theme" id="theme" aria-pressed="false" aria-label="Basculer le thème clair/sombre"><svg><use href="#i-moon"/></svg></button>
    <div class="eyebrow">${esc(input.project)} · Rapport de clôture</div>
    <h1>${esc(input.title)}</h1>
    <div class="meta">Change <code>${esc(input.change)}</code> · rapport généré le ${esc(input.generated)}
      · suivi <code>${esc(input.file)}</code> · tâches <code>${esc(input.tasksFile)}</code></div>
    <div class="kpis">
      <div class="kpi"><div class="l">Terminées</div><div class="v" style="color:var(--done)">${done}<small style="font-size:12px;color:var(--muted)">/${total}</small></div></div>
      <div class="kpi"><div class="l">Avancement</div><div class="v" style="color:var(--brand)">${percent}<small style="font-size:12px;color:var(--muted)">%</small></div></div>
      <div class="kpi"><div class="l">Écarts</div><div class="v" style="color:${ecarts.length ? "var(--bad)" : "var(--done)"}">${ecarts.length}</div></div>
      <div class="kpi"><div class="l">Reste</div><div class="v" style="color:var(--muted)">${doing + todo}<small style="font-size:12px;color:var(--muted)"> +${blocked} bloquées</small></div></div>
    </div>
    <div class="bar"><i></i></div>
    <div class="bar-cap">${done}/${total} tâches terminées · ${percent} %</div>
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
<script>
(function(){
  "use strict";
  var root = document.documentElement;
  var btn = document.getElementById("theme");
  var use = btn ? btn.querySelector("use") : null;
  function apply(t){
    root.setAttribute("data-theme", t);
    if(btn) btn.setAttribute("aria-pressed", t === "dark" ? "true" : "false");
    if(use) use.setAttribute("href", t === "dark" ? "#i-sun" : "#i-moon");
  }
  var saved = null;
  try { saved = localStorage.getItem("sdlc-theme"); } catch(e) {}
  apply(saved || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  if(btn){
    btn.addEventListener("click", function(){
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
      try { localStorage.setItem("sdlc-theme", next); } catch(e) {}
    });
  }
})();
</script>
</body>
</html>
`
}
