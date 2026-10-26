/**
 * Tests des hooks : chaque décision est exercée sans OpenCode, avec un exécuteur
 * de scripts et un git simulés.
 *
 * Deux ensembles de tests sont volontairement groupés ici (un par famille de
 * hook) plutôt qu'en un fichier par hook comme l'annonçait le plan : même
 * couverture, moins de duplication de montage.
 */
import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { createHarness } from "./harness.ts"
import { makeDeps } from "../tools/shared.ts"
import type { Deps } from "../tools/shared.ts"
import { decideCommit, installCommitGuard } from "../hooks/commit-guard.ts"
import { commandSucceeded, generateAfterValidate, installAfterValidate } from "../hooks/after-validate.ts"
import { signalAfterWrite } from "../hooks/after-write.ts"
import { alertOnIdle, sessionOf } from "../hooks/idle-alert.ts"
import { changeOfPath, isGitCommit, openspecValidateChange, stripQuoted } from "../hooks/shared.ts"

const REPO = resolve(import.meta.dirname, "fixtures/repo")

type Setup = { deps: Deps; harness: ReturnType<typeof createHarness>; scripts: { code: number; stdout: string }[] }

function setupFor(init: {
  directory: string
  options?: Record<string, unknown>
  env?: Record<string, string | undefined>
  checkCode?: number
  checkOutput?: string
  generateCode?: number
  generateOutput?: string
  gitOut?: { staged?: string; status?: string }
}): Setup {
  const harness = createHarness({ directory: init.directory, options: init.options ?? {} })
  const scripts: { code: number; stdout: string }[] = []
  const runScript = async (script: string, args: string[]) => {
    scripts.push({ code: 0, stdout: `${script} ${args.join(" ")}` })
    if (script.includes("check_sync.py")) {
      return { code: init.checkCode ?? 0, stdout: init.checkOutput ?? "sync OK : 25 tâche(s)", stderr: "" }
    }
    if (script.includes("generate.py")) {
      return { code: init.generateCode ?? 0, stdout: init.generateOutput ?? "→ 25 tâches / 7 lots", stderr: "" }
    }
    return { code: 0, stdout: "ok", stderr: "" }
  }
  const deps = makeDeps(harness.ctx, {
    runScript,
    runGit: async (args) => {
      if (args[0] === "diff") return { code: 0, stdout: init.gitOut?.staged ?? "", stderr: "" }
      return { code: 0, stdout: init.gitOut?.status ?? "", stderr: "" }
    },
  }, init.env ?? {})
  return { deps, harness, scripts }
}

test("la reconnaissance d'un commit ne confond pas une recherche avec un commit", () => {
  assert.equal(isGitCommit("git commit -m 'x'"), true)
  assert.equal(isGitCommit("git -C /tmp commit --amend"), true)
  assert.equal(isGitCommit("git add -A && git commit -m 'y'"), true)
  assert.equal(isGitCommit('rg "git commit" docs/'), false)
  assert.equal(isGitCommit("git status --porcelain"), false)
  assert.equal(stripQuoted('echo "git commit"'), "echo  ")
})

test("un commit en dérive est refusé, avec la correction à jouer", async () => {
  const { deps } = setupFor({
    directory: REPO,
    checkCode: 1,
    checkOutput: "DÉSYNCHRONISATION : 2.1 : suivi=done mais tasks.md case= ",
    gitOut: { staged: "openspec/changes/add-x/tasks.md\n" },
  })
  const decision = await decideCommit(deps, "git commit -m 'x'")
  assert.equal(decision?.block, true)
  assert.match(decision!.message, /commit refusé/)
  assert.match(decision!.message, /2\.1/)
  assert.match(decision!.message, /sdlc_track/)
})

test("un commit synchrone passe et porte le verdict", async () => {
  const { deps } = setupFor({
    directory: REPO,
    gitOut: { staged: "docs/suivi-add-x.html\n" },
  })
  const decision = await decideCommit(deps, "git commit -m 'x'")
  assert.equal(decision?.block, false)
  assert.match(decision!.message, /suivi synchrone/)
})

test("sans chemin indexé, l'arbre de travail sert de périmètre", async () => {
  const { deps } = setupFor({
    directory: REPO,
    gitOut: { staged: "", status: " M docs/suivi-add-x.html\n?? openspec/changes/add-x/tasks.md\n" },
  })
  const decision = await decideCommit(deps, "git commit -m 'x'")
  assert.equal(decision?.block, false)
  assert.equal(deps.config.blockCommit, true)
})

test("rien à contrôler et interrupteur d'urgence : aucun blocage", async () => {
  const empty = setupFor({ directory: REPO, gitOut: { staged: "", status: "" } })
  const decision = await decideCommit(empty.deps, "git commit -m 'x'")
  assert.equal(decision?.block, false)
  assert.match(decision!.message, /rien à contrôler/)

  const killed = setupFor({ directory: REPO, env: { AI_SDLC_TRACKER: "off" }, gitOut: { staged: "x" } })
  const off = await decideCommit(killed.deps, "git commit -m 'x'")
  assert.equal(off?.block, false)
  assert.match(off!.message, /interrupteur d'urgence/)
})

test("commit-guard s'installe : le hook before lève, le hook after ajoute le verdict", async () => {
  const { deps, harness } = setupFor({
    directory: REPO,
    checkCode: 1,
    checkOutput: "dérive : 3.2",
    gitOut: { staged: "openspec/changes/add-x/tasks.md\n" },
  })
  await installCommitGuard(harness.ctx, deps)

  await assert.rejects(
    () => harness.fireHook("execute.before", { tool: "bash", input: { command: "git commit -m x" } }),
    /commit refusé/,
  )

  const event = { tool: "bash", input: { command: "git commit -m x" }, result: { content: "sortie du shell" } }
  await harness.fireHook("execute.after", event)
  assert.match(String((event.result as { content: string }).content), /sortie du shell\n\[ai-sdlc-tracker\]/)
})

test("un dépassement de délai au commit est un refus explicite, distinct d'une dérive", async () => {
  const { deps } = setupFor({
    directory: REPO,
    checkCode: 124,
    checkOutput: "[ai-sdlc-tracker] timeout après 10000 ms",
    gitOut: { staged: "openspec/changes/add-x/tasks.md" },
  })
  const decision = await decideCommit(deps, "git commit -m x")
  assert.equal(decision?.block, true)
  assert.match(decision!.message, /timeout/)
  assert.match(decision!.message, /n'a pas rendu la main/)
  assert.doesNotMatch(decision!.message, /désynchronisé/)
})

test("la validation stricte déclenche la génération, jamais --all", async () => {
  assert.equal(openspecValidateChange("openspec validate add-x --strict"), "add-x")
  assert.equal(openspecValidateChange("openspec validate --all"), undefined)
  assert.equal(openspecValidateChange("npm test"), undefined)
  assert.equal(commandSucceeded({ status: "completed" }), true)
  assert.equal(commandSucceeded({ status: "error" }), false)
  assert.equal(commandSucceeded({}), undefined)

  const { deps, scripts } = setupFor({ directory: REPO })
  const event = {
    tool: "bash",
    input: { command: "openspec validate add-x --strict" },
    status: "completed",
    result: { content: "" },
  }
  const message = await generateAfterValidate(deps, event)
  assert.match(message!, /suivi créé|suivi régénéré/)
  assert.ok(
    scripts.some((call) => call.stdout.includes("generate.py") && call.stdout.includes("--tasks")),
    "le générateur est appelé avec le tasks.md",
  )
  assert.ok(
    scripts.some((call) => call.stdout.includes("--eyebrow repo")),
    "l'en-tête porte le nom du dépôt (défaut dérivé)",
  )

  const all = await generateAfterValidate(deps, { tool: "bash", input: { command: "openspec validate --all" } })
  assert.equal(all, undefined)
  const failed = await generateAfterValidate(deps, {
    tool: "bash",
    input: { command: "openspec validate add-x --strict" },
    status: "error",
    result: { content: "" },
  })
  assert.equal(failed, undefined)
  const disabled = setupFor({ directory: REPO, options: { autoGenerate: false } })
  assert.equal(
    await generateAfterValidate(disabled.deps, {
      tool: "bash",
      input: { command: "openspec validate add-x --strict" },
      status: "completed",
      result: { content: "" },
    }),
    undefined,
  )
})

test("after-validate s'installe et annonce dans la sortie", async () => {
  const { deps, harness } = setupFor({ directory: REPO })
  await installAfterValidate(harness.ctx, deps)
  const event = {
    tool: "bash",
    input: { command: "openspec validate add-x --strict" },
    status: "completed",
    result: { content: "validation ok" },
  }
  await harness.fireHook("execute.after", event)
  const content = String((event.result as { content: string }).content)
  assert.match(content, /ai-sdlc-tracker\] suivi/)
  assert.match(content, /Demander à l'utilisateur s'il veut l'ouvrir/)
})

test("une écriture directe est signalée, jamais refusée (chemins absolus des outils réels)", async () => {
  const drift = setupFor({ directory: REPO, checkCode: 1, checkOutput: "2.1 : suivi=done mais tasks.md case= " })
  const message = await signalAfterWrite(drift.deps, {
    tool: "edit",
    input: { filePath: join(REPO, "openspec/changes/add-x/tasks.md") },
  })
  assert.match(message!, /divergent/)
  assert.match(message!, /Change concerné : add-x/)
  assert.match(message!, /sdlc_track/)
  assert.ok(
    drift.scripts.some((call) => call.stdout.includes("--paths openspec/changes/add-x/tasks.md")),
    "le chemin absolu est ramené dans le dépôt avant d'être passé au script",
  )
  assert.ok(
    !drift.scripts.some((call) => call.stdout.includes(REPO)),
    "aucun chemin absolu n'est passé au script",
  )

  const clean = setupFor({ directory: REPO })
  const okMessage = await signalAfterWrite(clean.deps, {
    tool: "edit",
    input: { filePath: join(REPO, "docs/suivi-add-x.html") },
  })
  assert.match(okMessage!, /suivi synchrone/)

  const unrelated = await signalAfterWrite(clean.deps, {
    tool: "edit",
    input: { filePath: join(REPO, "docs/guide-plugins-opencode.html") },
  })
  assert.equal(unrelated, undefined)

  const otherTool = await signalAfterWrite(clean.deps, { tool: "read", input: { filePath: "docs/suivi-add-x.html" } })
  assert.equal(otherTool, undefined)
})

test("l'alerte de fin de tour est muette par défaut et synthétique si activée", async () => {
  assert.equal(sessionOf({ properties: { sessionID: "ses_1" } }), "ses_1")
  assert.equal(sessionOf({}), undefined)

  const off = setupFor({ directory: REPO, checkCode: 1, gitOut: { staged: "a" } })
  assert.equal(await alertOnIdle(off.deps, { type: "session.idle" }), undefined)

  const on = setupFor({
    directory: REPO,
    options: { alertOnIdle: true },
    checkCode: 1,
    checkOutput: "dérive",
    gitOut: { staged: "openspec/changes/add-x/tasks.md" },
  })
  const message = await alertOnIdle(on.deps, { type: "session.idle", properties: { sessionID: "ses_1" } })
  assert.match(message!, /désynchronisé/)
  assert.equal(on.harness.synthetic.length, 1)
  assert.equal(on.harness.prompts.length, 0, "aucun tour de génération n'est relancé")

  const noSession = await alertOnIdle(on.deps, { type: "session.idle" })
  assert.match(noSession!, /désynchronisé/)
  assert.equal(on.harness.synthetic.length, 1, "sans identifiant de session, rien n'est déposé")
})

test("les identifiants de change sont déduits des chemins suivis", () => {
  assert.equal(changeOfPath("docs/suivi-add-x.html"), "add-x")
  assert.equal(changeOfPath("docs/suivi-multi.html"), undefined)
  assert.equal(changeOfPath("openspec/changes/add-x/tasks.md"), "add-x")
  assert.equal(
    changeOfPath("openspec/changes/archive/2026-10-13-add-push-channel-self-service/tasks.md"),
    "add-push-channel-self-service",
  )
  assert.equal(changeOfPath("docs/README.md"), undefined)
})

test("un dépôt non suivi laisse passer le commit et le dit", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-none-"))
  mkdirSync(join(dir, "docs"), { recursive: true })
  writeFileSync(join(dir, "docs", "notes.md"), "rien à voir")
  const { deps } = setupFor({ directory: dir, gitOut: { staged: "docs/notes.md" } })
  const decision = await decideCommit(deps, "git commit -m 'x'")
  assert.equal(decision?.block, false)
  assert.match(decision!.message, /aucun change OpenSpec/)
})
