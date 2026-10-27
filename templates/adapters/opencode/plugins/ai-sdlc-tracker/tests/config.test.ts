import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { DEFAULT_CONFIG, detectScope, gatesEnabled, resolveConfig } from "../core.ts"

const REPO = resolve(import.meta.dirname, "fixtures/repo")

test("les défauts sont ceux du design, sans nom de projet en dur", () => {
  const config = resolveConfig({}, {}, "/tmp/mon-depot")
  assert.deepEqual(config, {
    ...DEFAULT_CONFIG,
    projectName: "mon-depot",
    pythonBin: "python3",
    killed: false,
  })
  assert.equal(config.alertOnIdle, false)
  assert.equal(config.strict, false)
  assert.equal(config.scriptsDir, ".agents/skills/suivi-taches")
  assert.equal(config.checkScript, "scripts/check_sync.py")
  assert.equal(config.commandTimeoutMs, 10_000)
})

test("le nom de projet est déduit du dépôt, et la configuration reste prioritaire", () => {
  assert.equal(resolveConfig({}, {}, "/tmp/mon-depot").projectName, "mon-depot")
  assert.equal(resolveConfig({ projectName: "Autre" }, {}, "/tmp/mon-depot").projectName, "Autre")
  assert.equal(resolveConfig({}, {}, "").projectName, "projet")
})

test("le binaire Python suit la plateforme, et une valeur configurée gagne", () => {
  const config = resolveConfig({}, {}, "/tmp/x")
  assert.equal(config.pythonBin, process.platform === "win32" ? "python" : "python3")
  assert.equal(resolveConfig({ pythonBin: "python3.12" }, {}, "/tmp/x").pythonBin, "python3.12")
})

test("le délai des commandes est positif, sinon le défaut s'applique", () => {
  assert.equal(resolveConfig({ commandTimeoutMs: 2500 }, {}, "/tmp/x").commandTimeoutMs, 2500)
  assert.equal(resolveConfig({ commandTimeoutMs: 0 }, {}, "/tmp/x").commandTimeoutMs, 10_000)
  assert.equal(resolveConfig({ commandTimeoutMs: -5 }, {}, "/tmp/x").commandTimeoutMs, 10_000)
  assert.equal(resolveConfig({ commandTimeoutMs: "10" }, {}, "/tmp/x").commandTimeoutMs, 10_000)
})

test("l'interrupteur d'urgence coupe les gates, quelles que soient les options", () => {
  const config = resolveConfig({ strict: true, enabled: true }, { AI_SDLC_TRACKER: "off" }, "/tmp/x")
  assert.equal(config.killed, true)
  assert.equal(gatesEnabled(config), false)

  for (const value of ["OFF", "0", "false"]) {
    assert.equal(resolveConfig({}, { AI_SDLC_TRACKER: value }, "/tmp/x").killed, true, `valeur ${value}`)
  }
  assert.equal(resolveConfig({}, { AI_SDLC_TRACKER: "on" }, "/tmp/x").killed, false)
  assert.equal(resolveConfig({}, {}, "/tmp/x").killed, false)
})

test("une option inconnue est ignorée et un type invalide retombe sur le défaut", () => {
  const config = resolveConfig(
    {
      inconnue: "peu importe",
      blockCommit: "oui",
      projectName: "   ",
      scriptsDir: 42,
      alertOnIdle: true,
    },
    {},
    "/tmp/mon-depot",
  )
  assert.equal(config.blockCommit, DEFAULT_CONFIG.blockCommit)
  assert.equal(config.projectName, "mon-depot")
  assert.equal(config.scriptsDir, DEFAULT_CONFIG.scriptsDir)
  assert.equal(config.alertOnIdle, true)
  assert.equal("inconnue" in config, false)
})

test("un répertoire sans change ni suivi est classé inactif, sans exception", () => {
  const empty = mkdtempSync(join(tmpdir(), "sdlc-none-"))
  const scope = detectScope(empty)
  assert.equal(scope.scope, "none")
  assert.match(scope.message, /inactif/)
})

test("le dépôt de test est reconnu comme dépôt suivi", () => {
  const scope = detectScope(REPO)
  assert.equal(scope.scope, "tracked")
  assert.match(scope.message, /\d+ change\(s\) OpenSpec/)
})
