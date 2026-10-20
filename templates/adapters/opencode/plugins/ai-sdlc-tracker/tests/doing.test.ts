import test from "node:test"
import assert from "node:assert/strict"
import { canStartTask, type TaskState } from "../core.ts"

const task = (id: string, status: string, note = ""): TaskState => ({
  id,
  lot: id.split(".")[0],
  status,
  updated: "2026-10-19",
  note,
  title: "",
})

test("ouverture refusée quand une autre tâche du lot est en cours sans note", () => {
  const tasks = [task("2.3", "doing"), task("2.4", "todo")]
  const decision = canStartTask(tasks, "2.4")
  assert.equal(decision.ok, false)
  if (decision.ok) return
  assert.equal(decision.blocking.id, "2.3")
  assert.match(decision.message, /2\.3 est déjà en cours sans note/)
  assert.match(decision.message, /sdlc_track 2\.3 done\|blocked/)
})

test("une tâche en cours AVEC note ne bloque pas (elle documente son état)", () => {
  const tasks = [task("2.3", "doing", "Fait : schéma écrit ; vérifié : 3 tests."), task("2.4", "todo")]
  assert.deepEqual(canStartTask(tasks, "2.4"), { ok: true })
})

test("une tâche bloquée avec note n'empêche pas d'ouvrir la suivante", () => {
  const tasks = [task("2.3", "blocked", "Bloquée par dépendance : identifiants opérateur."), task("2.4", "todo")]
  assert.deepEqual(canStartTask(tasks, "2.4"), { ok: true })
})

test("un forçage sans raison est refusé", () => {
  const tasks = [task("2.3", "doing")]
  const decision = canStartTask(tasks, "2.4", { force: true, reason: "   " })
  assert.equal(decision.ok, false)
  if (decision.ok) return
  assert.match(decision.message, /forçage refusé/)
})

test("un forçage avec raison est accepté", () => {
  const tasks = [task("2.3", "doing")]
  assert.deepEqual(canStartTask(tasks, "2.4", { force: true, reason: "tâches indépendantes, lot parallèle" }), { ok: true })
})

test("un autre lot n'est jamais bloqué, et rouvrir la même tâche non plus", () => {
  const tasks = [task("2.3", "doing"), task("3.1", "todo"), task("2.4", "todo")]
  assert.deepEqual(canStartTask(tasks, "3.1"), { ok: true })
  assert.deepEqual(canStartTask(tasks, "2.3"), { ok: true })
  assert.deepEqual(canStartTask(tasks, "5.2"), { ok: true })
})
