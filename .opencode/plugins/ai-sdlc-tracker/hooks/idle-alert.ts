/**
 * Abonnement `session.idle` — alerte de fin de tour, **désactivée par défaut**.
 *
 * C'est le seul filet pour une dérive qui ne produit aucun commit (le travail
 * continue, le commit viendra plus tard ou jamais). Elle n'est pas activée parce
 * que la liste des points d'application retenue ne l'inclut pas : `alertOnIdle:
 * true` dans les options du dépôt la met en service.
 *
 * L'alerte passe par un message **synthétique** : visible dans la conversation,
 * elle ne relance aucun tour de génération (on alerte, on ne boucle pas).
 */
import { inactive } from "../tools/shared.ts"
import type { Deps } from "../tools/shared.ts"
import type { HookEvent, TrackerContext } from "../types.ts"
import { guarded } from "./guarded.ts"
import { commitPaths, verdictFor } from "./shared.ts"

/** Identifiant de session d'un événement `session.idle` (forme vérifiée à l'exécution). */
export function sessionOf(event: HookEvent): string | undefined {
  const properties = event.properties as { sessionID?: unknown } | undefined
  if (typeof properties?.sessionID === "string") return properties.sessionID
  if (typeof event.sessionID === "string") return event.sessionID
  return undefined
}

export async function alertOnIdle(deps: Deps, event: HookEvent): Promise<string | undefined> {
  if (event.type !== "session.idle") return undefined
  if (!deps.config.alertOnIdle) return undefined

  const off = inactive(deps)
  if (off) return undefined // un dépôt non suivi ne mérite pas d'alerte à chaque tour

  const paths = await commitPaths(deps)
  if (paths.length === 0) return undefined
  const verdict = await verdictFor(deps, paths)
  if (verdict.ok) return undefined

  const sessionID = sessionOf(event)
  const message =
    `[ai-sdlc-tracker] ⚠ Le suivi est désynchronisé avec tasks.md :\n${verdict.message}\n` +
    `Rejouer sdlc_track, une tâche à la fois.`
  if (!sessionID) return message // l'appelant journalise : mieux qu'un silence

  await deps.ctx.session.synthetic({ sessionID, text: message })
  return message
}

export async function installIdleAlert(ctx: TrackerContext, deps: Deps): Promise<() => void> {
  const controller = new AbortController()
  const onEvent = guarded("idle-alert", async (event: HookEvent) => {
    const message = await alertOnIdle(deps, event)
    if (message && !sessionOf(event)) console.warn(message)
  })
  void (async () => {
    try {
      for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
        await onEvent(event)
      }
    } catch {
      // Best-effort : un flux interrompu ne doit jamais casser la session.
    }
  })()
  return () => controller.abort()
}
