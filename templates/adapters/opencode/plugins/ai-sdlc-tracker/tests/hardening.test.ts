/**
 * Tests du durcissement : isolation des hooks, bornes de temps, filtre de chemins.
 *
 * Ces trois propriétés ne sont pas des détails : sans elles, un bug du plugin
 * casse la session (constaté), un script bloqué la gèle, et le filtre trop large
 * produit du bruit à chaque rédaction de document.
 */
import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { spawnCommand } from "../core.ts"
import { BlockError, guarded } from "../hooks/guarded.ts"
import { TRACKED_PATH, relativize } from "../hooks/shared.ts"
import { installAfterWrite } from "../hooks/after-write.ts"
import { createHarness } from "./harness.ts"
import { makeDeps } from "../tools/shared.ts"

const REPO = resolve(import.meta.dirname, "fixtures/repo")

test("un refus volontaire remonte, une erreur interne est avalée", async () => {
  const warnings: string[] = []
  const original = console.warn
  console.warn = (...args: unknown[]) => warnings.push(args.map(String).join(" "))

  try {
    const block = guarded("test-block", () => {
      throw new BlockError("refus volontaire")
    })
    await assert.rejects(() => block({}), /refus volontaire/)

    const broken = guarded("test-broken", () => {
      throw new Error("panne interne")
    })
    await broken({})

    assert.equal(warnings.length, 1)
    assert.match(warnings[0], /test-broken/)
    assert.match(warnings[0], /panne interne/)
    assert.match(warnings[0], /session préservée/)
  } finally {
    console.warn = original
  }
})

test("un hook en panne ne fait pas échouer l'appel d'outil", async () => {
  const h = createHarness({ directory: REPO })
  const warnings: string[] = []
  const original = console.warn
  console.warn = (...args: unknown[]) => warnings.push(args.map(String).join(" "))

  try {
    const deps = makeDeps(
      h.ctx,
      {
        runScript: async () => {
          throw new Error("script introuvable")
        },
        runGit: async () => ({ code: 0, stdout: "", stderr: "" }),
      },
      {},
    )
    await installAfterWrite(h.ctx, deps)

    const event = {
      tool: "edit",
      input: { filePath: join(REPO, "openspec/changes/add-x/tasks.md") },
      result: { content: "écriture faite" },
    }
    await h.fireHook("execute.after", event)

    assert.equal((event.result as { content: string }).content, "écriture faite", "la sortie n'est pas altérée")
    assert.equal(warnings.length, 1)
    assert.match(warnings[0], /after-write/)
  } finally {
    console.warn = original
  }
})

test("une commande qui ne rend pas la main est arrêtée dans le délai", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-timeout-"))
  const started = Date.now()
  const result = await spawnCommand("node", ["-e", "setTimeout(() => {}, 5000)"], dir, { timeoutMs: 200 })
  const elapsed = Date.now() - started

  assert.equal(result.code, 124)
  assert.match(result.stderr, /timeout après 200 ms/)
  assert.ok(elapsed < 2000, `arrêt attendu rapidement, obtenu en ${elapsed} ms`)
})

test("sans délai explicite, la borne par défaut s'applique", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sdlc-timeout-default-"))
  const result = await spawnCommand("node", ["-e", "process.exit(0)"], dir)
  assert.equal(result.code, 0)
})

test("le filtre de chemins ne retient que tasks.md et les suivis", () => {
  const tracked = [
    "openspec/changes/add-x/tasks.md",
    "openspec/changes/archive/2026-10-13-add-push-channel-self-service/tasks.md",
    "docs/suivi-add-x.html",
    "docs/suivi-multi.html",
  ]
  const ignored = [
    "openspec/changes/add-x/proposal.md",
    "openspec/changes/add-x/design.md",
    "openspec/changes/add-x/specs/sdlc-tracking/spec.md",
    "docs/guide-plugins-opencode.html",
    "docs/README.md",
  ]
  for (const path of tracked) assert.equal(TRACKED_PATH.test(path), true, path)
  for (const path of ignored) assert.equal(TRACKED_PATH.test(path), false, path)
})

test("le plugin n'ouvre jamais un fichier de lui-même", async () => {
  const { readdirSync } = await import("node:fs")
  const { readFileSync } = await import("node:fs")
  const root = resolve(import.meta.dirname, "..")
  const sources: string[] = []

  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === "node_modules" || entry.name === "tests") continue
      const path = join(dir, entry.name)
      if (entry.isDirectory()) walk(path)
      else if (entry.name.endsWith(".ts")) sources.push(path)
    }
  }
  walk(root)

  assert.ok(sources.length >= 10, "les sources sont bien parcourues")
  for (const file of sources) {
    const code = readFileSync(file, "utf-8")
    assert.doesNotMatch(
      code,
      /spawn(Command)?\(\s*["'](open|xdg-open|start)["']/,
      `${file} ne doit pas lancer d'ouverture`,
    )
    assert.doesNotMatch(code, /exec(File)?\(\s*["'](open|xdg-open)["']/, `${file} ne doit pas lancer d'ouverture`)
  }
})

test("les chemins absolus sont ramenés dans le dépôt, les chemins externes écartés", () => {
  assert.deepEqual(
    relativize("/repo", ["/repo/docs/suivi-x.html", "/repo/openspec/changes/add-x/tasks.md"]),
    ["docs/suivi-x.html", "openspec/changes/add-x/tasks.md"],
  )
  assert.deepEqual(relativize("/repo", ["/autre/docs/suivi-x.html", "../evade.md"]), [])
})
