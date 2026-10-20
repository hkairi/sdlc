import { copyFileSync, mkdirSync, mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { resolve, join } from "node:path"
import test from "node:test"
import assert from "node:assert/strict"
import { findTasksFile, parseMonoTasks, parseMultiFeatures, resolveTarget } from "../core.ts"

const REPO = resolve(import.meta.dirname, "fixtures/repo")

test("un change avec suivi mono est résolu en mono", () => {
  const result = resolveTarget(REPO, "add-x")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.target.kind, "mono")
  assert.equal(result.target.file, "docs/suivi-add-x.html")
  assert.equal(result.target.tasksFile, "openspec/changes/add-x/tasks.md")
  assert.ok(result.target.tasks.length > 0, "les tâches du suivi sont lues")
  assert.ok(result.target.tasks.every((t) => t.status !== ""), "chaque tâche porte un statut")
})

test("un change référencé par le suivi multi est résolu en multi, avec sa clé de feature", () => {
  // Sur ce dépôt, le suivi mono est prioritaire : add-x a les deux.
  const mono = resolveTarget(REPO, "add-x")
  assert.equal(mono.ok, true)
  if (!mono.ok) return
  assert.equal(mono.target.kind, "mono")

  // Cas du suivi multi seul (dépôt qui n'a pas de suivi mono pour ce change).
  const dir = mkdtempSync(join(tmpdir(), "sdlc-multi-"))
  mkdirSync(join(dir, "docs"), { recursive: true })
  copyFileSync(resolve(REPO, "docs/suivi-multi.html"), join(dir, "docs/suivi-multi.html"))

  const result = resolveTarget(dir, "add-x")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.target.kind, "multi")
  assert.equal(result.target.file, "docs/suivi-multi.html")
  assert.equal(result.target.feature, "add-x")
  assert.match(result.target.tasksFile, /openspec\/changes\/add-x\/tasks\.md$/)
  assert.ok(result.target.tasks.length > 0)
})

test("un identifiant inconnu ne renvoie rien et liste les suivis candidats", () => {
  const result = resolveTarget(REPO, "change-qui-nexiste-pas")
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.match(result.message, /aucun suivi pour le change/)
  assert.match(result.message, /sdlc_generate/)
  assert.ok(result.candidates.some((c) => c.includes("docs/suivi-")), "des candidats sont proposés")
})

test("un fichier de suivi forcé est respecté et annoncé", () => {
  const forced = resolveTarget(REPO, "add-x", "docs/suivi-add-x.html")
  assert.equal(forced.ok, true)
  if (!forced.ok) return
  assert.equal(forced.target.file, "docs/suivi-add-x.html")

  const missing = resolveTarget(REPO, "add-x", "docs/suivi-inexistant.html")
  assert.equal(missing.ok, false)
  if (missing.ok) return
  assert.match(missing.message, /introuvable/)
})

test("le tasks.md d'un change archivé est retrouvé", () => {
  assert.equal(
    findTasksFile(REPO, "add-y"),
    "openspec/changes/archive/2026-10-13-add-y/tasks.md",
  )
  assert.equal(findTasksFile(REPO, "vraiment-inexistant"), undefined)
})

test("les analyseurs lisent le HTML mono et le bloc feature-data du multi", () => {
  const html = `<div class="task" data-id="2.1" data-status="doing" data-updated="2026-10-19">
      <em class="note">Fait : <b>x</b> ; vérifié : 3 tests.</em>
      <span class="draft-flag"></span></div>`
  const mono = parseMonoTasks(html)
  assert.deepEqual(mono, [
    {
      id: "2.1",
      lot: "2",
      status: "doing",
      updated: "2026-10-19",
      note: "Fait : x ; vérifié : 3 tests.",
      title: "",
    },
  ])

  const multi = `<script type="application/json" id="feature-data">
    {"features":[{"id":"f","change":"add-x","tasks_file":"openspec/changes/add-x/tasks.md",
      "tasks":[{"id":"1.1","lot":"L1","status":"done","updated":"2026-10-01","note":"n"}]}]}</script>`
  const features = parseMultiFeatures(multi)
  assert.equal(features.length, 1)
  assert.equal(features[0].key, "f")
  assert.equal(features[0].tasks[0].status, "done")

  assert.deepEqual(parseMultiFeatures("<div></div>"), [])
  assert.deepEqual(parseMultiFeatures('<script type="application/json" id="feature-data">{oops}</script>'), [])
})
