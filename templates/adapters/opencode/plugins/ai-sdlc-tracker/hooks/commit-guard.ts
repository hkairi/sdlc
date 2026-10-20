/**
 * Hook `execute.before` — un commit lancé par l'agent avec un suivi désynchronisé
 * est refusé, avec le détail et la correction à jouer.
 *
 * Pourquoi ici : c'est le seul endroit qui peut refuser *pendant* la session. Le
 * hook git couvre le terminal (quand il est installé) et la CI couvre le push,
 * mais ni l'un ni l'autre ne voit un agent qui travaille.
 *
 * Écart assumé par rapport à la première rédaction du plan : pas de repli sur
 * `check_sync.py --all`, qui échoue sur la dette historique du dépôt (six changes
 * anciens sans suivi) et bloquerait donc tous les commits. On contrôle les chemins
 * touchés (index, sinon arbre de travail), comme le faisait le plugin V1 et comme
 * le fait `.githooks/pre-commit`.
 */
import { inactive } from "../tools/shared.ts"
import type { Deps } from "../tools/shared.ts"
import type { HookEvent, ToolDef, TrackerContext } from "../types.ts"
import { BlockError, guarded } from "./guarded.ts"
import { appendToResult, commitPaths, commandOf, correctionHint, isGitCommit, verdictFor } from "./shared.ts"

/** Décision pour une commande : bloque-t-elle ? (`undefined` = rien à faire) */
export async function decideCommit(
  deps: Deps,
  command: string,
): Promise<{ block: boolean; message: string } | undefined> {
  if (!isGitCommit(command)) return undefined
  if (!deps.config.blockCommit) return undefined

  const off = inactive(deps)
  if (off) return { block: false, message: off }

  const paths = await commitPaths(deps)
  if (paths.length === 0) {
    return { block: false, message: "[ai-sdlc-tracker] rien à contrôler (aucun chemin modifié ni indexé)" }
  }

  const verdict = await verdictFor(deps, paths, true)
  if (verdict.ok) return { block: false, message: `[ai-sdlc-tracker] suivi synchrone — ${verdict.message}` }

  if (verdict.timedOut) {
    return {
      block: true,
      message:
        `[ai-sdlc-tracker] commit refusé : timeout — le contrôle n'a pas rendu la main dans le délai ` +
        `(${deps.config.commandTimeoutMs} ms). Ce n'est pas une dérive constatée, mais le suivi n'a pas pu ` +
        `être vérifié. Rejouer le commit, ou vérifier \`${deps.config.checkScript}\` à la main.`,
    }
  }

  return {
    block: true,
    message:
      `[ai-sdlc-tracker] commit refusé : le suivi est désynchronisé avec tasks.md.\n${verdict.message}\n` +
      correctionHint(),
  }
}

export function commitGuardTool(_deps: Deps): ToolDef | undefined {
  return undefined
}

/** Enregistre le garde : blocage avant, verdict ajouté après. */
export async function installCommitGuard(ctx: TrackerContext, deps: Deps): Promise<void> {
  await ctx.tool.hook(
    "execute.before",
    guarded("commit-guard (avant)", async (event: HookEvent) => {
      if (!isShellTool(event)) return
      const decision = await decideCommit(deps, commandOf(event.input))
      if (decision?.block) throw new BlockError(decision.message)
    }),
  )

  await ctx.tool.hook(
    "execute.after",
    guarded("commit-guard (après)", async (event: HookEvent) => {
      if (!isShellTool(event)) return
      const decision = await decideCommit(deps, commandOf(event.input))
      if (!decision) return
      appendToResult(event, decision.message)
    }),
  )
}

function isShellTool(event: HookEvent): boolean {
  return event.tool === "bash" || event.tool === "shell"
}
