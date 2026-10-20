/**
 * Plugin `ai-sdlc-tracker` — applique la règle de suivi d'avancement dans la session.
 *
 * Le module exporte une définition PAR DÉFAUT avec un `id` et une fonction `setup` :
 * c'est exactement ce qui manquait au plugin V1 `suivi-sync.ts`, qui échouait au
 * chargement (API V1 sur un serveur V2) sans que rien ne le signale dans l'interface.
 *
 * Répartition : la méthode reste dans la skill `suivi-taches` (chargée à la demande,
 * partagée avec les autres outils) ; ce plugin porte l'exécution (six outils typés)
 * et l'application (quatre points de contrôle).
 */
import { Plugin } from "@opencode/plugin"
import type { Editor, ToolDef, TrackerContext } from "./types.ts"
import { NAMESPACE, inactive, makeDeps } from "./tools/shared.ts"
import type { Deps } from "./tools/shared.ts"
import { defineCheck } from "./tools/check.ts"
import { defineDoctor } from "./tools/doctor.ts"
import { defineGenerate } from "./tools/generate.ts"
import { definePhase } from "./tools/phase.ts"
import { defineReport } from "./tools/report.ts"
import { defineStatus } from "./tools/status.ts"
import { defineTrack } from "./tools/track.ts"
import { installCommitGuard } from "./hooks/commit-guard.ts"
import { installAfterValidate } from "./hooks/after-validate.ts"
import { installAfterWrite } from "./hooks/after-write.ts"
import { installIdleAlert } from "./hooks/idle-alert.ts"
import { logHookFailure } from "./hooks/guarded.ts"

export const PLUGIN_ID = "ai-sdlc-tracker"

export const TOOL_DEFINITIONS = [
  defineCheck,
  defineTrack,
  definePhase,
  defineGenerate,
  defineStatus,
  defineReport,
  defineDoctor,
] as const

/** Enregistre les six outils sous le namespace `sdlc`. */
export async function registerTools(ctx: TrackerContext, deps: Deps): Promise<void> {
  await ctx.tool.transform((editor: Editor) => {
    editor.namespace({ name: NAMESPACE, description: "Suivi d'avancement OpenSpec (ai-sdlc-tracker)" })
    for (const define of TOOL_DEFINITIONS) {
      const tool: ToolDef = define(deps)
      editor.add(tool)
    }
  })
}

/** Tout le câblage du plugin ; renvoie la fonction de nettoyage. */
export async function createTracker(ctx: TrackerContext): Promise<() => void> {
  const directory = ctx.location.directory
  if (!directory) throw new Error("[ai-sdlc-tracker] contexte sans répertoire de projet")

  const deps = makeDeps(ctx)
  let stop: () => void = () => {}

  // Chaque installation est isolée : un contrôle qui ne s'installe pas ne prive
  // pas des autres, et les outils restent disponibles.
  const installs: { name: string; run: () => Promise<unknown> }[] = [
    { name: "outils", run: () => registerTools(ctx, deps) },
  ]

  const scope = inactive(deps)
  if (scope) {
    // Fail-open assumé : hors périmètre (ou interrupteur d'urgence), aucun blocage.
    console.warn(`${scope} — outils disponibles, contrôles inactifs`)
  } else {
    installs.push(
      { name: "commit-guard", run: () => installCommitGuard(ctx, deps) },
      { name: "after-validate", run: () => installAfterValidate(ctx, deps) },
      { name: "after-write", run: () => installAfterWrite(ctx, deps) },
      { name: "idle-alert", run: () => installIdleAlert(ctx, deps) },
    )
  }

  for (const install of installs) {
    try {
      const result = await install.run()
      if (typeof result === "function") stop = result as () => void
    } catch (error) {
      logHookFailure(install.name, error)
    }
  }

  return stop
}

export default Plugin.define({
  id: PLUGIN_ID,
  async setup(ctx) {
    return createTracker(ctx as unknown as TrackerContext)
  },
})
