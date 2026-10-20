/**
 * `sdlc_phase` — coche ou décoche un item de phase, puis régénère le suivi.
 *
 * La phase `impl` est dérivée des tâches : elle est refusée ici, avec le renvoi
 * vers `sdlc_track`. En multi, l'item est préfixé par la clé de la feature.
 */
import { resolveTarget, scriptPath } from "../core.ts"
import { failure, inactive, optionalString, sdlcTool, scriptText, text } from "./shared.ts"
import type { Deps } from "./shared.ts"
import type { ToolDef } from "../types.ts"

const STATUSES = ["todo", "doing", "blocked", "done"]

/**
 * Identifiants réels des phases dans le suivi généré. Le nom affiché est
 * « Planification », mais l'identifiant est `plan` : `track_phase.py` ne trouve
 * rien avec `planification` et répond sans erreur (constaté le 2026-10-19 en
 * clôturant les deux changes — les items restaient à `todo`).
 */
const PHASE_IDS: Record<string, string> = { planification: "plan" }

export function definePhase(deps: Deps): ToolDef {
  return sdlcTool({
    name: "phase",
    description:
      "Met à jour un item de phase du suivi (validation.tests, cloture.archive, …) avec une note datée, " +
      "puis régénère le HTML. La phase « impl » est dérivée des tâches : la mettre à jour avec sdlc_track.",
    input: {
      type: "object",
      properties: {
        change: { type: "string" },
        phase: {
          type: "string",
          enum: ["cadrage", "planification", "impl", "validation", "deploy", "cloture"],
        },
        item: { type: "string", description: "identifiant d'item dans la phase, par exemple tests" },
        status: { type: "string", enum: STATUSES },
        note: { type: "string" },
        file: { type: "string", description: "fichier de suivi à forcer (mono ou multi)" },
      },
      required: ["change", "phase", "item", "status"],
      additionalProperties: false,
    },
    async execute(input) {
      const off = inactive(deps)
      if (off) return text(off)

      const change = optionalString(input, "change") ?? failure("argument « change » requis")
      const phase = optionalString(input, "phase") ?? failure("argument « phase » requis")
      const item = optionalString(input, "item") ?? failure("argument « item » requis")
      const status = optionalString(input, "status") ?? failure("argument « status » requis")
      const note = optionalString(input, "note")

      if (phase === "impl") {
        return text(
          "phase impl refusée : elle est dérivée des tâches. Utiliser sdlc_track " +
            "(le statut des tâches met la phase à jour toute seule).",
        )
      }
      if (!STATUSES.includes(status)) return text(`statut inconnu « ${status} » : attendu ${STATUSES.join(", ")}`)

      const resolved = resolveTarget(deps.directory, change, optionalString(input, "file"), deps.readFile)
      if (!resolved.ok) {
        return text(`phase refusée : ${resolved.message}\nSuivis disponibles : ${resolved.candidates.join(", ")}`)
      }
      const { target } = resolved
      const phaseId = PHASE_IDS[phase] ?? phase
      const ident = target.kind === "multi" ? `${target.feature}:${phaseId}.${item}` : `${phaseId}.${item}`
      const args = ["--file", target.file, ident, status]
      if (note) args.push(note)

      const result = await deps.runScript(scriptPath(deps.config, "track_phase.py"), args, deps.directory)

      // Contrôle optimiste : un identifiant inconnu fait répondre le script sans
      // erreur, donc sans effet. On relit l'état au lieu de l'affirmer.
      const warnings: string[] = []
      if (result.code === 0) {
        const actual = readPhaseItem(deps, target, phaseId, item)
        if (actual !== undefined && actual !== status) {
          warnings.push(
            `⚠ ${phaseId}.${item} n'est pas à « ${status} » dans ${target.file} après la mise à jour ` +
              `(lu : ${actual}) — vérifier l'identifiant de phase ou d'item ; le script n'a rien appliqué.`,
          )
        }
      }

      return text([`${target.file} · ${ident} → ${status}`, scriptText("phase", result), ...warnings].join("\n"))
    },
  })
}

/** Statut réellement présent dans le bloc de phases du suivi mono (multi : non vérifié). */
export function readPhaseItem(
  deps: Deps,
  target: { kind: string; file: string },
  phaseId: string,
  itemId: string,
): string | undefined {
  if (target.kind !== "mono") return undefined
  try {
    const content = deps.readFile(target.file)
    const raw = /<script type="application\/json" id="phase-data">([\s\S]*?)<\/script>/.exec(content)?.[1]
    if (!raw) return undefined
    const data = JSON.parse(raw) as { phases?: { id?: string; items?: { id?: string; status?: string }[] }[] }
    const phase = data.phases?.find((candidate) => candidate.id === phaseId)
    return phase?.items?.find((candidate) => candidate.id === itemId)?.status
  } catch {
    return undefined
  }
}
