import test from "node:test"
import assert from "node:assert/strict"
import { parseStateJson } from "../core.ts"

const STATE = JSON.stringify({
  schema: 1,
  meta: { title: "Suivi" },
  features: [
    {
      id: "auth-sso",
      name: "Authentification SSO",
      change: "auth-sso",
      tasks_file: "openspec/changes/auth-sso/tasks.md",
      tasks: [
        {
          id: "1.1",
          lot: "L1",
          title: "Modèle de session",
          status: "done",
          updated: "2026-10-10",
          note: "Fait : table sessions ; vérifié : 12 tests, 0 échec.",
          executor: "codex",
          reviewer: "claude",
          review_iteration: 1,
          escalated: false,
          ready_to_commit: true,
          commit_message: "feat(auth): table sessions",
        },
        { id: "1.2", lot: "L1", title: "Migration", status: "todo", updated: "", note: "" },
      ],
    },
  ],
})

test("parseStateJson lit les tâches et leurs rôles depuis state.json", () => {
  const result = parseStateJson(STATE)
  assert.equal(result.ok, true)
  if (!result.ok) return
  assert.equal(result.schema, 1)
  assert.equal(result.features.length, 1)

  const feature = result.features[0]
  assert.equal(feature.id, "auth-sso")
  assert.equal(feature.change, "auth-sso")
  assert.equal(feature.tasksFile, "openspec/changes/auth-sso/tasks.md")

  const [done, todo] = feature.tasks
  assert.equal(done.id, "1.1")
  assert.equal(done.executor, "codex")
  assert.equal(done.reviewer, "claude")
  assert.equal(done.review_iteration, 1)
  assert.equal(done.escalated, false)
  assert.equal(done.ready_to_commit, true)
  assert.equal(done.commit_message, "feat(auth): table sessions")

  // Rôles absents → null, jamais inventés (« rien n'est inventé »).
  assert.equal(todo.executor, null)
  assert.equal(todo.reviewer, null)
  assert.equal(todo.review_iteration, null)
  assert.equal(todo.escalated, false)
  assert.equal(todo.ready_to_commit, false)
  assert.equal(todo.commit_message, null)
})

test("parseStateJson refuse un schéma non reconnu", () => {
  const result = parseStateJson(JSON.stringify({ schema: 2, features: [] }))
  assert.equal(result.ok, false)
  if (!result.ok) assert.match(result.reason, /schéma/)
})

test("parseStateJson refuse un JSON invalide", () => {
  const result = parseStateJson("{ pas du json")
  assert.equal(result.ok, false)
  if (!result.ok) assert.match(result.reason, /illisible/)
})

test("parseStateJson tolère des features vides", () => {
  const result = parseStateJson(JSON.stringify({ schema: 1, features: [] }))
  assert.equal(result.ok, true)
  if (result.ok) assert.equal(result.features.length, 0)
})
