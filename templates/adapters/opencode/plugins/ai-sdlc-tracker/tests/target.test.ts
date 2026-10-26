import test from "node:test"
import assert from "node:assert/strict"
import { resolve } from "node:path"
import { findTasksFile, resolveTarget } from "../core.ts"

const REPO = resolve(import.meta.dirname, "fixtures/repo")

test("un change est résolu depuis state.json", () => {
  const result = resolveTarget(REPO, "add-x")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.target.kind, "state")
  assert.equal(result.target.file, "docs/suivi-add-x.html")
  assert.equal(result.target.stateFile, "docs/suivi/state.json")
  assert.equal(result.target.feature, "add-x")
  assert.equal(result.target.tasksFile, "openspec/changes/add-x/tasks.md")
  assert.equal(result.target.tasks.length, 3)
  assert.ok(result.target.tasks.every((t) => t.status !== ""), "chaque tâche porte un statut")
})

test("un change archivé est résolu par sa feature (tasks_file)", () => {
  const result = resolveTarget(REPO, "add-y")
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.target.feature, "add-y")
  assert.equal(result.target.tasksFile, "openspec/changes/archive/2026-10-13-add-y/tasks.md")
  assert.equal(result.target.tasks[0].status, "done")
})

test("un identifiant inconnu ne renvoie rien et liste les candidats", () => {
  const result = resolveTarget(REPO, "change-qui-nexiste-pas")
  assert.equal(result.ok, false)
  if (result.ok) return
  assert.match(result.message, /ne référence pas le change/)
  assert.ok(result.candidates.includes("docs/suivi/state.json"), "state.json est proposé")
})

test("un fichier d'état forcé est respecté, un chemin absent est refusé", () => {
  const forced = resolveTarget(REPO, "add-x", "docs/suivi/state.json")
  assert.equal(forced.ok, true)
  if (!forced.ok) return
  assert.equal(forced.target.stateFile, "docs/suivi/state.json")

  const missing = resolveTarget(REPO, "add-x", "docs/suivi/inexistant.json")
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
