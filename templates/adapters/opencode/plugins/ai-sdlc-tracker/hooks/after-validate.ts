/**
 * Hook `execute.after` — après une validation OpenSpec stricte réussie, le suivi
 * du change est généré (ou créé s'il n'existe pas), et la sortie de la commande
 * l'annonce.
 *
 * Déclencheur volontairement étroit : `openspec validate <id>` avec un identifiant
 * explicite, jamais `--all` (régénérer dix-sept suivis sur une commande de contrôle
 * global serait un effet de bord inacceptable), et seulement si la commande a
 * réussi. Une seule exécution par commande.
 */
import { existsSync } from "node:fs"
import { join } from "node:path"
import { findTasksFile, scriptPath } from "../core.ts"
import { inactive } from "../tools/shared.ts"
import type { Deps } from "../tools/shared.ts"
import type { HookEvent, TrackerContext } from "../types.ts"
import { guarded } from "./guarded.ts"
import { appendToResult, commandOf, openspecValidateChange } from "./shared.ts"
import { changeTitle } from "../tools/generate.ts"

/** La commande a-t-elle réussi ? (`undefined` si l'état n'est pas exploitable) */
export function commandSucceeded(event: HookEvent): boolean | undefined {
  const status = typeof event.status === "string" ? event.status : undefined
  if (status === "error" || status === "failed") return false
  if (status === "completed" || status === "success") return true
  const code = typeof event.exitCode === "number" ? event.exitCode : undefined
  if (code !== undefined) return code === 0
  return undefined
}

export async function generateAfterValidate(deps: Deps, event: HookEvent): Promise<string | undefined> {
  if (!deps.config.autoGenerate) return undefined
  const change = openspecValidateChange(commandOf(event.input))
  if (!change) return undefined
  if (commandSucceeded(event) === false) return undefined

  const off = inactive(deps)
  if (off) return off

  const script = scriptPath(deps.config, "generate.py")
  if (!existsSync(join(deps.directory, script))) {
    return `[ai-sdlc-tracker] suivi non généré : ${script} introuvable (option scriptsDir « ${deps.config.scriptsDir} »)`
  }

  const tasksFile = findTasksFile(deps.directory, change)
  if (!tasksFile) return undefined

  const existing = join(deps.directory, "docs", `suivi-${change}.html`)
  const created = !existsSync(existing)
  const result = await deps.runScript(
    script,
    [
      "--out", `docs/suivi-${change}.html`,
      "--tasks", tasksFile,
      "--title",
      `Suivi d'avancement — ${changeTitle(deps.directory, change, deps.readFile)} · ${deps.config.projectName}`,
      "--eyebrow",
      `${deps.config.projectName} · Suivi d'avancement`,
    ],
    deps.directory,
  )
  const detail = `${result.stdout}${result.stderr}`.trim().split("\n").slice(-1)[0] ?? ""
  if (result.code !== 0) {
    return `[ai-sdlc-tracker] suivi non ${created ? "créé" : "régénéré"} pour ${change} (code ${result.code}) : ${detail}`
  }
  return `[ai-sdlc-tracker] suivi ${created ? "créé" : "régénéré"} : docs/suivi-${change}.html — ${detail} Demander à l'utilisateur s'il veut l'ouvrir ; ne pas l'ouvrir sans accord.`
}

export async function installAfterValidate(ctx: TrackerContext, deps: Deps): Promise<void> {
  await ctx.tool.hook(
    "execute.after",
    guarded("after-validate", async (event: HookEvent) => {
      const message = await generateAfterValidate(deps, event)
      if (message) appendToResult(event, message)
    }),
  )
}
