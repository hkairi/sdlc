import test from "node:test"
import assert from "node:assert/strict"
import { createHarness } from "./harness.ts"
import mod, { PLUGIN_ID, createTracker } from "../index.ts"

test("le module exporte par défaut une définition avec id et setup", () => {
  const def = mod as unknown as { id?: string; setup?: unknown }
  assert.equal(def.id, PLUGIN_ID)
  assert.equal(typeof def.setup, "function")
  assert.equal(PLUGIN_ID, "ai-sdlc-tracker")
})

test("setup s'exécute avec un contexte conforme", async () => {
  const h = createHarness({ directory: "/tmp/depot" })
  await mod.setup(h.ctx as never)
  assert.equal(h.ctx.location.directory, "/tmp/depot")
})

test("createTracker refuse un contexte sans répertoire de projet", async () => {
  const h = createHarness()
  await assert.rejects(
    () => createTracker({ ...h.ctx, location: { directory: "" } }),
    /contexte sans répertoire de projet/,
  )
})
