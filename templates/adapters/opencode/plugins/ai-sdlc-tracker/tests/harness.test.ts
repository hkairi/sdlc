import test from "node:test"
import assert from "node:assert/strict"
import { createHarness, effectiveToolName } from "./harness.ts"

test("le nom effectif d'un outil suit la composition d'OpenCode", () => {
  assert.equal(effectiveToolName("sdlc", "check"), "sdlc_check")
  assert.equal(effectiveToolName(undefined, "check"), "check")
  assert.equal(effectiveToolName("a.b", "trace"), "a_b_trace")
})

test("un outil enregistré dans un namespace est capturé sous son nom effectif", async () => {
  const h = createHarness()
  await h.ctx.tool.transform((editor) => {
    editor.namespace({ name: "sdlc", description: "Suivi" })
    editor.add({ name: "check", description: "contrôle" })
    editor.add({
      name: "track",
      description: "mise à jour",
      execute: async () => ({ content: "ok" }),
    })
  })

  assert.deepEqual([...h.tools.keys()].sort(), ["sdlc_check", "sdlc_track"])
  assert.deepEqual(await h.callTool("sdlc_track", {}), { content: "ok" })
})

test("un hook enregistré est capturé et exécuté", async () => {
  const h = createHarness()
  await h.ctx.tool.hook("execute.before", (event) => {
    if (event.tool === "bash") throw new Error("bloqué")
  })

  assert.equal(h.hooks["execute.before"]?.length, 1)
  await assert.rejects(() => h.fireHook("execute.before", { tool: "bash" }), /bloqué/)
  await h.fireHook("execute.before", { tool: "read" })
})

test("les abonnements d'événements s'arrêtent à l'abandon", async () => {
  const h = createHarness({ events: [{ type: "session.idle" }, { type: "session.idle" }] })
  const seen: string[] = []
  for await (const event of h.ctx.event.subscribe()) {
    seen.push(String(event.type))
  }
  assert.deepEqual(seen, ["session.idle", "session.idle"])

  h.abort()
  const after: string[] = []
  for await (const event of h.ctx.event.subscribe()) after.push(String(event.type))
  assert.deepEqual(after, [])
})

test("l'exécuteur simulé capture les appels de scripts", async () => {
  const h = createHarness({ respond: () => ({ code: 1, stdout: "dérive", stderr: "" }) })
  const result = await h.runScript(".agents/skills/suivi-taches/scripts/track.py", ["--file", "x.html"], h.ctx.location.directory)

  assert.equal(result.code, 1)
  assert.equal(result.stdout, "dérive")
  assert.deepEqual(h.calls, [
    { script: ".agents/skills/suivi-taches/scripts/track.py", args: ["--file", "x.html"], cwd: h.ctx.location.directory },
  ])
})
