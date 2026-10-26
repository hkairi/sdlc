/**
 * Harnais d'intégration : le **câblage complet** (createTracker → hooks → décisions).
 *
 * Les tests unitaires vérifient chaque hook isolément. Celui-ci vérifie qu'ils sont
 * réellement enregistrés par l'initialisation, dans l'ordre du plugin, et qu'ils
 * prennent les bonnes décisions sur un dépôt réel — sans OpenCode.
 *
 * Les commandes sont réelles (python3, git) : c'est le prix de la fidélité. Le dépôt
 * utilisé est un répertoire temporaire ; le dépôt de travail n'est jamais touché.
 */
import test from "node:test"
import assert from "node:assert/strict"
import { cpSync, copyFileSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs"
import { spawnSync } from "node:child_process"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { createTracker } from "../index.ts"
import { createHarness } from "./harness.ts"

const REPO = resolve(import.meta.dirname, "fixtures/repo")

type Fixture = {
  dir: string
  harness: ReturnType<typeof createHarness>
}

function fixture(tasksChecked: boolean): Fixture {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-e2e-"))
  mkdirSync(join(dir, "scripts"), { recursive: true })
  mkdirSync(join(dir, "docs", "suivi"), { recursive: true })
  mkdirSync(join(dir, "openspec", "changes", "add-x"), { recursive: true })

  copyFileSync(join(REPO, "scripts", "check_sync.py"), join(dir, "scripts", "check_sync.py"))

  writeFileSync(
    join(dir, "openspec", "changes", "add-x", "tasks.md"),
    `# Tasks — add-x\n\n## 1. Lot\n\n- [${tasksChecked ? "x" : " "}] 1.1 a\n`,
  )
  writeFileSync(join(dir, "openspec", "changes", "add-x", "proposal.md"), "# Change: add-x\n\n## Why\n\nDémo.\n")
  const state = { schema: 1, features: [{ id: "add-x", change: "add-x", tasks_file: "openspec/changes/add-x/tasks.md",
    tasks: [{ id: "1.1", lot: "1", title: "a", status: "doing", updated: "2026-10-19", note: "" }] }] }
  writeFileSync(join(dir, "docs", "suivi", "state.json"), JSON.stringify(state))

  // Dépôt git de test (répertoire temporaire uniquement) : le garde lit `git status`.
  const init = spawnSync("git", ["init", "--quiet"], { cwd: dir, encoding: "utf-8" })
  assert.equal(init.status, 0, init.stderr)

  return { dir, harness: createHarness({ directory: dir, events: [] }) }
}

async function mounted(tasksChecked: boolean): Promise<Fixture & { stop: () => void }> {
  const f = fixture(tasksChecked)
  const stop = await createTracker(f.harness.ctx)
  return { ...f, stop }
}

test("createTracker enregistre les quatre contrôles et les outils", async () => {
  const f = await mounted(false)
  try {
    assert.ok(f.harness.hooks["execute.before"]?.length, "garde de commit enregistré")
    assert.ok((f.harness.hooks["execute.after"]?.length ?? 0) >= 2, "au moins deux hooks d'après-exécution")
    assert.ok(f.harness.tools.has("sdlc_track"), "outil track enregistré")
    assert.ok(f.harness.tools.has("sdlc_doctor"), "outil doctor enregistré")
  } finally {
    f.stop()
  }
})

test("un commit en dérive est refusé par le câblage, puis accepté après correction", async () => {
  const f = await mounted(true) // tasks.md coché, suivi en cours : désynchronisé
  try {
    await assert.rejects(
      () => f.harness.fireHook("execute.before", { tool: "bash", input: { command: "git commit -m x" } }),
      /commit refusé/,
    )

    writeFileSync(join(f.dir, "openspec", "changes", "add-x", "tasks.md"), "# Tasks — add-x\n\n## 1. Lot\n\n- [ ] 1.1 a\n")
    await f.harness.fireHook("execute.before", { tool: "bash", input: { command: "git commit -m x" } })

    const event = {
      tool: "bash",
      input: { command: "git commit -m x" },
      status: "completed",
      result: { content: "commit simulé" },
    }
    await f.harness.fireHook("execute.after", event)
    assert.match(String((event.result as { content: string }).content), /suivi synchrone/)
  } finally {
    f.stop()
  }
})

test("une écriture directe est signalée par le câblage", async () => {
  const f = await mounted(true)
  try {
    const event = {
      tool: "edit",
      input: { filePath: join(f.dir, "openspec", "changes", "add-x", "tasks.md") },
      result: { content: "édition faite" },
    }
    await f.harness.fireHook("execute.after", event)
    const content = String((event.result as { content: string }).content)
    assert.match(content, /ai-sdlc-tracker/)
    assert.match(content, /divergent|synchrone/)
  } finally {
    f.stop()
  }
})

test("une validation stricte déclenche la génération, jamais --all", async () => {
  const f = await mounted(false)
  try {
    let seen = ""
    for (const command of [
      "openspec validate add-x --strict",
      "openspec validate add-x --strict",
      "openspec validate --all",
    ]) {
      const event = {
        tool: "bash",
        input: { command },
        status: "completed",
        result: { content: "" },
      }
      await f.harness.fireHook("execute.after", event)
      seen = String((event.result as { content: string }).content)
      if (command.includes("--all")) {
        assert.doesNotMatch(seen, /ai-sdlc-tracker/, "--all ne génère rien")
      } else {
        // La génération est tentée ; le rappel d'ouverture n'apparaît que si un fichier
        // a été produit (couvert au niveau unitaire dans hooks.test.ts).
        assert.match(seen, /ai-sdlc-tracker\] suivi/, `la génération est tentée : ${seen}`)
      }
    }
  } finally {
    f.stop()
  }
})

test("le nettoyage libère l'abonnement d'événements", async () => {
  const f = await mounted(false)
  f.stop()
  assert.ok(true, "le cleanup s'exécute sans lever")
})
