/**
 * `sdlc_generate` — crée ou régénère le suivi d'un change (ou le suivi multi).
 *
 * Le générateur one-shot de la skill écrit un titre et un en-tête avec le nom
 * d'un autre projet : le plugin passe donc explicitement `--title` et `--eyebrow`
 * construits sur l'option `projectName`, au lieu de modifier le script vendorisé
 * (ce qui créerait une dérive). `--all` n'est pas exposé : impossible de
 * régénérer tous les suivis par accident.
 */
import { existsSync, readdirSync } from "node:fs"
import { join } from "node:path"
import { findTasksFile, scriptPath } from "../core.ts"
import {
  failure,
  inactive,
  optionalBoolean,
  optionalString,
  sdlcTool,
  scriptText,
  text,
} from "./shared.ts"
import type { Deps } from "./shared.ts"
import type { ToolDef } from "../types.ts"

/** Chemin du `proposal.md` d'un change, y compris archivé. */
export function proposalPath(directory: string, change: string): string | undefined {
  const direct = join("openspec", "changes", change, "proposal.md")
  if (existsSync(join(directory, direct))) return direct
  const archive = join(directory, "openspec", "changes", "archive")
  if (!existsSync(archive)) return undefined
  const entry = readdirSync(archive).find(
    (name) => (name === change || name.endsWith(`-${change}`)) && existsSync(join(archive, name, "proposal.md")),
  )
  return entry ? join("openspec", "changes", "archive", entry, "proposal.md") : undefined
}

/** Titre du change, lu dans son `proposal.md` (`# Change: …`). */
export function changeTitle(directory: string, change: string, readFile: Deps["readFile"]): string {
  const rel = proposalPath(directory, change)
  if (!rel) return change
  const first = (readFile(rel).split("\n")[0] ?? "").replace(/^#\s*Change\s*:\s*/i, "").trim()
  return first || change
}

export function defineGenerate(deps: Deps): ToolDef {
  return sdlcTool({
    name: "generate",
    description:
      "Crée le suivi d'un change s'il n'existe pas, ou le régénère sans perte (statuts, dates, notes, phases " +
      "conservés), et ajoute la ligne de docs/README.md. multi: true régénère docs/suivi-multi.html depuis son " +
      "manifeste. Ne régénère jamais tous les suivis d'un coup.",
    input: {
      type: "object",
      properties: {
        change: { type: "string", description: "identifiant exact du change OpenSpec" },
        multi: { type: "boolean", description: "régénérer le suivi multi-chantiers" },
        strictDetails: { type: "boolean", description: "exiger les détails de tâche (défaut : oui)" },
      },
      required: ["change"],
      additionalProperties: false,
    },
    async execute(input) {
      const off = inactive(deps)
      if (off) return text(off)

      const change = optionalString(input, "change") ?? failure("argument « change » requis")
      const script = scriptPath(deps.config, "generate.py")
      if (!existsSync(join(deps.directory, script))) {
        return text(`generate refusé : ${script} introuvable (option scriptsDir « ${deps.config.scriptsDir} »)`)
      }

      if (optionalBoolean(input, "multi") === true) {
        const result = await deps.runScript(
          script,
          ["--out", "docs/suivi-multi.html", "--manifest", "docs/suivi-multi.json"],
          deps.directory,
        )
        return text(scriptText("generate multi", result))
      }

      const tasksFile = findTasksFile(deps.directory, change)
      if (!tasksFile) {
        return text(`generate refusé : openspec/changes/${change}/tasks.md introuvable — vérifier l'identifiant du change.`)
      }

      const title = changeTitle(deps.directory, change, deps.readFile)
      const out = join("docs", `suivi-${change}.html`)
      const args = [
        "--out", out,
        "--tasks", tasksFile,
        "--title", `Suivi d'avancement — ${title} · ${deps.config.projectName}`,
        "--eyebrow", `${deps.config.projectName} · Suivi d'avancement`,
      ]
      const result = await deps.runScript(script, args, deps.directory)
      return text(
        `${out} généré\n${scriptText("generate", result)}\n` +
          `Demander à l'utilisateur s'il veut l'ouvrir (open ${out}) ; ne pas l'ouvrir sans accord.`,
      )
    },
  })
}
