/**
 * Tests des six outils. Un seul fichier pour les six (le plan en annonçait un par
 * outil) : même couverture, un montage partagé au lieu de six.
 *
 * Rien n'est écrit dans le dépôt réel : les outils sont exercés avec un exécuteur
 * de scripts simulé et, pour `report`, dans un répertoire temporaire.
 */
import test from "node:test"
import assert from "node:assert/strict"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { createHarness } from "./harness.ts"
import { makeDeps } from "../tools/shared.ts"
import type { Deps } from "../tools/shared.ts"
import { defineCheck } from "../tools/check.ts"
import { defineTrack } from "../tools/track.ts"
import { definePhase } from "../tools/phase.ts"
import { defineGenerate, changeTitle, proposalPath } from "../tools/generate.ts"
import { defineStatus, collectChantiers } from "../tools/status.ts"
import { defineReport } from "../tools/report.ts"
import { defineDoctor } from "../tools/doctor.ts"

const REPO = resolve(import.meta.dirname, "fixtures/repo")

type Call = { script: string; args: string[] }

function mount(init: {
  directory?: string
  options?: Record<string, unknown>
  env?: Record<string, string | undefined>
  answer?: (script: string, args: string[]) => { code: number; stdout: string }
} = {}): { deps: Deps; calls: Call[]; gitCalls: string[][] } {
  const harness = createHarness({ directory: init.directory ?? REPO, options: init.options ?? {} })
  const calls: Call[] = []
  const gitCalls: string[][] = []
  const deps = makeDeps(
    harness.ctx,
    {
      runScript: async (script, args) => {
        calls.push({ script, args })
        const answer = init.answer?.(script, args) ?? { code: 0, stdout: "ok" }
        return { code: answer.code, stdout: answer.stdout, stderr: "" }
      },
      runGit: async (args) => {
        gitCalls.push(args)
        return { code: 0, stdout: "", stderr: "" }
      },
    },
    init.env ?? {},
  )
  return { deps, calls, gitCalls }
}

const content = (result: unknown): string => String((result as { content: string }).content)

test("sdlc_check délègue au script et refuse deux modes à la fois", async () => {
  const { deps, calls } = mount({ answer: () => ({ code: 0, stdout: "sync OK : 3 tâche(s)" }) })
  const tool = defineCheck(deps)

  const ok = await tool.execute!({ change: "add-x" })
  assert.match(content(ok), /check — docs\/suivi-add-x\.html/)
  assert.match(content(ok), /sync OK/)
  assert.equal(calls[0].args[0], "--file")
  assert.equal(calls[0].args[1], "docs/suivi-add-x.html")
  assert.equal(calls[0].args[2], "--tasks")
  // Le change a été archivé : le tasks.md vit sous openspec/changes/archive/<date>-<id>/.
  assert.match(calls[0].args[3], /openspec\/changes\/(archive\/\d{4}-\d{2}-\d{2}-)?add-x\/tasks\.md$/)

  const ambiguous = await tool.execute!({ change: "add-x", all: true })
  assert.match(content(ambiguous), /un seul mode à la fois/)

  const noMode = await tool.execute!({})
  assert.match(content(noMode), /préciser un mode/)

  const unknown = await tool.execute!({ change: "change-inexistant" })
  assert.match(content(unknown), /check refusé/)
  assert.equal(calls.length, 1, "un change inconnu n'appelle pas le script")
})

test("sdlc_check en mode chemins passe les chemins au script", async () => {
  const { deps, calls } = mount({ answer: () => ({ code: 1, stdout: "DÉSYNCHRONISATION" }) })
  const tool = defineCheck(deps)
  const result = await tool.execute!({ paths: ["docs/suivi-add-x.html"], requireEvidence: true })
  assert.match(content(result), /échec \(code 1\)/)
  assert.deepEqual(calls[0].args, ["--paths", "docs/suivi-add-x.html", "--require-evidence"])
})

test("sdlc_track met à jour mono et nomme le fichier", async () => {
  const { deps, calls } = mount({ answer: () => ({ code: 0, stdout: "1.1 -> done" }) })
  const tool = defineTrack(deps)

  const result = await tool.execute!({
    change: "add-x",
    task: "1.1",
    status: "done",
    note: "Fait : configuration ; vérifié : 42 tests, 0 échec.",
  })
  assert.match(content(result), /docs\/suivi-add-x\.html · add-x:1\.1 → done/)
  assert.equal(calls[0].args[0], "--file")
  assert.equal(calls[0].args[1], "docs/suivi-add-x.html")
  assert.equal(calls[0].args[2], "--feature")
  assert.equal(calls[0].args[3], "add-x")
  assert.equal(calls[0].args[4], "--tasks")
  assert.match(calls[0].args[5], /openspec\/changes\/add-x\/tasks\.md$/)
  assert.deepEqual(calls[0].args.slice(-3), ["1.1", "done", "Fait : configuration ; vérifié : 42 tests, 0 échec."])
  assert.equal(calls[0].script, ".agents/skills/suivi-taches/scripts/track.py")
})

test("sdlc_track refuse une tâche inconnue, un done sans note et un done sans preuve", async () => {
  const { deps, calls } = mount()
  const tool = defineTrack(deps)

  const unknown = await tool.execute!({ change: "add-x", task: "99.9", status: "todo" })
  assert.match(content(unknown), /introuvable/)

  const noNote = await tool.execute!({ change: "add-x", task: "1.1", status: "done" })
  assert.match(content(noNote), /note obligatoire/)

  const weak = await tool.execute!({ change: "add-x", task: "1.1", status: "done", note: "c'est fait" })
  assert.match(content(weak), /sans indice de vérification/)
  assert.equal(calls.length, 0, "aucun refus n'écrit dans le dépôt")
})

test("sdlc_track signale un relecteur absent ou égal à l'exécutant", async () => {
  const { deps } = mount()
  const tool = defineTrack(deps)

  const absent = await tool.execute!({
    change: "add-x", task: "1.1", status: "done",
    note: "Fait ; vérifié : 3 tests.",
  })
  assert.match(content(absent), /relecteur requis pour clore/)

  const same = await tool.execute!({
    change: "add-x", task: "1.1", status: "done",
    note: "Fait ; vérifié : 3 tests.",
    executor: "codex", reviewer: "codex",
  })
  assert.match(content(same), /ne peut pas être l'exécutant/)
})

test("sdlc_track refuse d'ouvrir deux tâches en cours dans le même lot", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-track-"))
  mkdirSync(join(dir, "docs", "suivi"), { recursive: true })
  mkdirSync(join(dir, "openspec", "changes", "add-x"), { recursive: true })
  writeFileSync(join(dir, "openspec", "changes", "add-x", "tasks.md"), "- [ ] 2.1 a\n- [ ] 2.2 b\n")
  const state = { schema: 1, features: [{ id: "add-x", change: "add-x", tasks_file: "openspec/changes/add-x/tasks.md", tasks: [
    { id: "2.1", lot: "2", title: "a", status: "doing", updated: "2026-10-19", note: "" },
    { id: "2.2", lot: "2", title: "b", status: "todo", updated: "", note: "" },
  ] }] }
  writeFileSync(join(dir, "docs", "suivi", "state.json"), JSON.stringify(state))

  const { deps, calls } = mount({ directory: dir })
  const tool = defineTrack(deps)
  const refused = await tool.execute!({ change: "add-x", task: "2.2", status: "doing" })
  assert.match(content(refused), /2\.1 est déjà en cours sans note/)
  assert.equal(calls.length, 0)

  const forced = await tool.execute!({
    change: "add-x",
    task: "2.2",
    status: "doing",
    force: true,
    reason: "tâches indépendantes",
  })
  assert.equal(calls.length, 1, "le forçage justifié écrit")
  assert.match(content(forced), /forçage : tâches indépendantes/)
})

test("sdlc_phase refuse la phase impl et préfixe la feature en multi", async () => {
  const { deps, calls } = mount({ answer: () => ({ code: 0, stdout: "phase ok" }) })
  const tool = definePhase(deps)

  const impl = await tool.execute!({ change: "add-x", phase: "impl", item: "x", status: "done" })
  assert.match(content(impl), /phase impl refusée/)
  assert.equal(calls.length, 0)

  const mono = await tool.execute!({
    change: "add-x",
    phase: "cadrage",
    item: "proposition",
    status: "done",
    note: "proposal + design validés (openspec validate --strict).",
  })
  assert.match(content(mono), /· cadrage\.proposition → done/)
  assert.deepEqual(calls[0].args.slice(-3), ["cadrage.proposition", "done", "proposal + design validés (openspec validate --strict)."])
  assert.equal(calls[0].script, ".agents/skills/suivi-taches/scripts/track_phase.py")
})

test("sdlc_generate vise le script vendorisé et impose le nom du projet", async () => {
  assert.match(proposalPath(REPO, "add-x") ?? "", /add-x\/proposal\.md$/)
  assert.equal(changeTitle(REPO, "add-x", (rel) => readFileSync(join(REPO, rel), "utf-8")), "add-x")

  const { deps, calls } = mount({ answer: () => ({ code: 0, stdout: "→ 3 tâches / 2 lots" }) })
  const tool = defineGenerate(deps)
  const result = await tool.execute!({ change: "add-x" })

  assert.equal(calls[0].script, ".agents/skills/suivi-taches/scripts/generate.py")
  assert.deepEqual(calls[0].args, [
    "--out", "docs/suivi-add-x.html",
    "--tasks", "openspec/changes/add-x/tasks.md",
    "--title", "Suivi d'avancement — add-x · repo",
    "--eyebrow", "repo · Suivi d'avancement",
  ])
  assert.match(content(result), /docs\/suivi-add-x\.html généré/)
  assert.match(content(result), /Demander à l'utilisateur s'il veut l'ouvrir/)

  const unknown = await tool.execute!({ change: "change-inexistant" })
  assert.match(content(unknown), /generate refusé/)

  const multi = await tool.execute!({ change: "x", multi: true })
  assert.equal(calls[1].script, ".agents/skills/suivi-taches/scripts/generate.py")
  assert.ok(calls[1].args.includes("docs/suivi-multi.json"))
  assert.match(content(multi), /generate multi/)
})

test("sdlc_status est en lecture seule, dédoublonne et signale l'ancienneté", async () => {
  const { deps, calls } = mount({ answer: () => ({ code: 1, stdout: JSON.stringify({ problems: ["un"] }) }) })
  const chantiers = collectChantiers(deps)
  const labels = chantiers.map((c) => c.label)
  assert.equal(new Set(labels).size, labels.length, "aucun chantier compté deux fois")
  assert.ok(labels.includes("add-x"))

  const result = await defineStatus(deps).execute!({ change: "add-x" })
  assert.match(content(result), /add-x — \d+\/3/)
  assert.match(content(result), /1 nouvelle\(s\) dérive\(s\)/)
  assert.deepEqual(calls.at(-1)!.args, ["--all", "--json"], "le contrôle de synchronisation est appelé en lecture seule")
})

test("sdlc_report écrit un HTML autonome et refuse d'écraser sans accord", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-report-"))
  mkdirSync(join(dir, "docs", "suivi"), { recursive: true })
  mkdirSync(join(dir, "openspec", "changes", "add-x"), { recursive: true })
  writeFileSync(join(dir, "openspec", "changes", "add-x", "tasks.md"), "- [x] 1.1 a\n")
  writeFileSync(join(dir, "openspec", "changes", "add-x", "proposal.md"), "# Change: Démonstration\n")
  const state = { schema: 1, features: [{ id: "add-x", change: "add-x", tasks_file: "openspec/changes/add-x/tasks.md", tasks: [
    { id: "1.1", lot: "1", title: "a", status: "done", updated: "2026-10-19", note: "Fait ; vérifié : 3 tests." },
  ] }] }
  writeFileSync(join(dir, "docs", "suivi", "state.json"), JSON.stringify(state))

  const { deps } = mount({ directory: dir })
  const tool = defineReport(deps)
  const first = await tool.execute!({ change: "add-x" })
  assert.match(content(first), /docs\/rapport-add-x\.html écrit \(1 tâches, 1 terminées, 0 bloquée\(s\)\)/)

  const report = readFileSync(join(dir, "docs", "rapport-add-x.html"), "utf-8")
  assert.match(report, /<title>Rapport de clôture — add-x/)
  assert.match(report, /Démonstration/)
  assert.match(report, /Fait ; vérifié : 3 tests\./)
  assert.doesNotMatch(report, /<script/i, "rapport sans script")
  assert.doesNotMatch(report, /https?:\/\//, "rapport sans ressource externe")

  const again = await tool.execute!({ change: "add-x" })
  assert.match(content(again), /existe déjà/)
  assert.ok(existsSync(join(dir, "docs", "rapport-add-x.html")))

  const overwrite = await tool.execute!({ change: "add-x", overwrite: true })
  assert.match(content(overwrite), /écrit/)
})

test("sdlc_doctor conclut et nomme les actions, sans écrire", async () => {
  const { deps, gitCalls } = mount({ answer: () => ({ code: 1, stdout: "" }) })
  const result = await defineDoctor(deps).execute!({})
  const output = content(result)

  assert.match(output, /^sdlc_doctor — (prêt|à corriger)/)
  assert.match(output, /version du plugin : 0\.2\.1/)
  assert.match(output, /périmètre : tracked/)
  assert.match(output, /script de contrôle : scripts\/check_sync\.py — présent/)
  assert.match(output, /vendorisation \(\.agents\/skills\/suivi-taches\) : complète/)
  assert.match(output, /python : python3/)
  assert.match(output, /hook git :/)
  assert.match(output, /baseline : \d{4}-\d{2}-\d{2} \(\d+ dérive\(s\) connue\(s\), \d+ tâche\(s\) sans preuve\)/)
  assert.match(output, /délai des commandes : 10000 ms/)
  assert.ok(gitCalls.some((args) => args[0] === "config"), "le hook git est interrogé")
})

test("sdlc_doctor nomme ce qui manque dans un dépôt vide", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-doctor-"))
  const { deps } = mount({ directory: dir, answer: () => ({ code: 0, stdout: "" }) })
  const output = content(await defineDoctor(deps).execute!({}))

  assert.match(output, /sdlc_doctor — à corriger/)
  assert.match(output, /périmètre : none/)
  assert.match(output, /ABSENT/)
  assert.match(output, /vérifier la skill suivi-taches/)
  assert.match(output, /installer le hook git/)
})

test("les outils sont muets hors périmètre ou sous interrupteur d'urgence", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-none-"))
  const { deps, calls } = mount({ directory: dir })
  for (const tool of [defineCheck(deps), defineTrack(deps), definePhase(deps), defineGenerate(deps), defineStatus(deps), defineReport(deps)]) {
    const result = await tool.execute!({ change: "x", task: "1.1", phase: "cadrage", item: "y", status: "todo" })
    assert.match(content(result), /inactif/)
  }
  const killed = mount({ directory: REPO, env: { AI_SDLC_TRACKER: "off" } })
  const result = await defineStatus(killed.deps).execute!({})
  assert.match(content(result), /interrupteur d'urgence/)
  assert.equal(calls.length, 0)
})

test("la baseline distingue la dette connue du neuf", async () => {
  const known = JSON.parse(readFileSync(join(REPO, ".agents/skills/suivi-taches/baseline.json"), "utf-8")) as { drifts: string[] }
  const knownDrift = known.drifts[0]

  const withKnown = mount({ answer: () => ({ code: 1, stdout: JSON.stringify({ problems: [knownDrift] }) }) })
  const output = content(await defineStatus(withKnown.deps).execute!({}))
  assert.match(output, /0 nouvelle\(s\) dérive\(s\) · 1 connue\(s\) depuis \d{4}-\d{2}-\d{2}/)

  const fresh = mount({ answer: () => ({ code: 1, stdout: JSON.stringify({ problems: ["add-neuf : tasks.md présent mais suivi manquant"] }) }) })
  const freshOut = content(await defineStatus(fresh.deps).execute!({}))
  assert.match(freshOut, /1 nouvelle\(s\) dérive\(s\) · 0 connue\(s\)/)
})

test("sans baseline, tout problème est nouveau mais l'état reste lisible", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-nobase-"))
  mkdirSync(join(dir, "docs", "suivi"), { recursive: true })
  const state = { schema: 1, features: [{ id: "add-x", change: "add-x", tasks: [
    { id: "1.1", lot: "1", title: "a", status: "done", updated: "2026-10-19", note: "Fait ; vérifié : 3 tests." },
  ] }] }
  writeFileSync(join(dir, "docs", "suivi", "state.json"), JSON.stringify(state))
  const { deps } = mount({ directory: dir, answer: () => ({ code: 1, stdout: JSON.stringify({ problems: ["x"] }) }) })
  const output = content(await defineStatus(deps).execute!({}))
  assert.match(output, /1 dérive\(s\)/)
})

function trackFixture(status: "todo" | "done"): string {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-concurrency-"))
  mkdirSync(join(dir, "docs", "suivi"), { recursive: true })
  mkdirSync(join(dir, "openspec", "changes", "add-x"), { recursive: true })
  writeFileSync(
    join(dir, "openspec", "changes", "add-x", "tasks.md"),
    `## 1. Lot\n\n- [${status === "done" ? "x" : " "}] 1.1 a\n`,
  )
  const state = { schema: 1, features: [{ id: "add-x", change: "add-x", tasks_file: "openspec/changes/add-x/tasks.md", tasks: [
    { id: "1.1", lot: "1", title: "a", status, updated: "2026-10-19", note: "" },
  ] }] }
  writeFileSync(join(dir, "docs", "suivi", "state.json"), JSON.stringify(state))
  return dir
}

test("une mise à jour non appliquée est signalée, pas présentée comme un succès", async () => {
  const dir = trackFixture("todo")
  const { deps } = mount({ directory: dir }) // script simulé qui n'écrit rien
  const result = await defineTrack(deps).execute!({
    change: "add-x",
    task: "1.1",
    status: "done",
    note: "Fait ; vérifié : 3 tests.",
  })
  const output = content(result)
  assert.match(output, /⚠ 1\.1 n'est pas à « done » dans docs\/suivi-add-x\.html/)
  assert.match(output, /un autre écrivain a pu modifier le fichier/)
  assert.match(output, /Relancer sdlc_track/)
})

test("une mise à jour déjà appliquée ne produit aucun avertissement", async () => {
  const dir = trackFixture("done")
  const { deps } = mount({ directory: dir })
  const result = await defineTrack(deps).execute!({
    change: "add-x",
    task: "1.1",
    status: "done",
    note: "Fait ; vérifié : 3 tests.",
    reviewer: "claude",
  })
  assert.doesNotMatch(content(result), /⚠/)
})

test("sdlc_phase traduit « planification » en identifiant réel « plan »", async () => {
  const { deps, calls } = mount({ answer: () => ({ code: 0, stdout: "ok" }) })
  await definePhase(deps).execute!({ change: "add-x", phase: "planification", item: "tasks", status: "done" })
  assert.ok(calls[0].args.includes("plan.tasks"), `arguments reçus : ${calls[0].args.join(" ")}`)
})

function phaseFixture(status: "todo" | "done"): string {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-phase-"))
  mkdirSync(join(dir, "docs", "suivi"), { recursive: true })
  mkdirSync(join(dir, "openspec", "changes", "add-x"), { recursive: true })
  writeFileSync(join(dir, "openspec", "changes", "add-x", "tasks.md"), "## 1. Lot\n\n- [ ] 1.1 a\n")
  const state = { schema: 1, features: [{ id: "add-x", change: "add-x", tasks_file: "openspec/changes/add-x/tasks.md",
    phases: [{ id: "plan", name: "Planification", items: [{ id: "tasks", status }] }],
    tasks: [{ id: "1.1", lot: "1", title: "a", status: "todo", updated: "", note: "" }] }] }
  writeFileSync(join(dir, "docs", "suivi", "state.json"), JSON.stringify(state))
  return dir
}

test("un item de phase non appliqué est signalé, pas présenté comme un succès", async () => {
  const dir = phaseFixture("todo")
  const { deps } = mount({ directory: dir })
  const output = content(
    await definePhase(deps).execute!({ change: "add-x", phase: "planification", item: "tasks", status: "done" }),
  )
  assert.match(output, /⚠ plan\.tasks n'est pas à « done »/)
  assert.match(output, /le script n'a rien appliqué/)
})

test("un item de phase déjà appliqué ne produit aucun avertissement", async () => {
  const dir = phaseFixture("done")
  const { deps } = mount({ directory: dir })
  const output = content(
    await definePhase(deps).execute!({ change: "add-x", phase: "planification", item: "tasks", status: "done" }),
  )
  assert.doesNotMatch(output, /⚠/)
})
