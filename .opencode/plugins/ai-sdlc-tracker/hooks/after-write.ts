/**
 * Hook `execute.after` — après une écriture directe de `tasks.md` ou d'un fichier
 * de suivi, l'état de synchronisation du change est ajouté à la sortie.
 *
 * On ne refuse jamais : rédiger les détails techniques et les critères
 * d'acceptation d'une tâche, ou corriger une formulation, sont des usages
 * normaux. L'objectif est la visibilité immédiate, pas l'interdiction.
 */
import { inactive } from "../tools/shared.ts"
import type { Deps } from "../tools/shared.ts"
import type { HookEvent, TrackerContext } from "../types.ts"
import { guarded } from "./guarded.ts"
import { TRACKED_PATH, appendToResult, changeOfPath, correctionHint, relativize, verdictFor, writtenPaths } from "./shared.ts"

const WRITE_TOOLS = new Set(["edit", "write", "patch", "multiedit", "multieditfiles"])

export async function signalAfterWrite(deps: Deps, event: HookEvent): Promise<string | undefined> {
  const tool = typeof event.tool === "string" ? event.tool : ""
  if (!WRITE_TOOLS.has(tool)) return undefined

  const paths = relativize(deps.directory, writtenPaths(event.input))
  const tracked = paths.filter((path) => TRACKED_PATH.test(path))
  if (tracked.length === 0) return undefined

  const off = inactive(deps)
  if (off) return off

  const verdict = await verdictFor(deps, tracked)
  const target = tracked.join(", ")
  if (verdict.ok) {
    return `[ai-sdlc-tracker] ${target} — suivi synchrone (${verdict.message})`
  }
  const change = tracked.map(changeOfPath).find(Boolean)
  return (
    `[ai-sdlc-tracker] ⚠ ${target} : le suivi et tasks.md divergent.\n${verdict.message}\n` +
    (change ? `Change concerné : ${change}. ` : "") +
    correctionHint()
  )
}

export async function installAfterWrite(ctx: TrackerContext, deps: Deps): Promise<void> {
  await ctx.tool.hook(
    "execute.after",
    guarded("after-write", async (event: HookEvent) => {
      const message = await signalAfterWrite(deps, event)
      if (message) appendToResult(event, message)
    }),
  )
}
