/**
 * `sdlc_report` — rapport de clôture d'un chantier, en HTML autonome.
 *
 * Lit le suivi (source de vérité) et sa table des tâches, écrit
 * `docs/rapport-<change>.html`, et refuse d'écraser un rapport existant sans
 * demande explicite. N'écrit jamais dans `tasks.md` ni dans le suivi.
 */
import { existsSync, mkdirSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { resolveTarget } from "../core.ts"
import { failure, inactive, optionalBoolean, optionalString, sdlcTool, text } from "./shared.ts"
import type { Deps } from "./shared.ts"
import type { ToolDef } from "../types.ts"
import { changeTitle } from "./generate.ts"
import { renderReport } from "./report-template.ts"

export function defineReport(deps: Deps): ToolDef {
  return sdlcTool({
    name: "report",
    description:
      "Écrit un rapport de clôture HTML autonome (docs/rapport-<change>.html) : progression, tâches avec " +
      "statut, date et note, écarts ouverts. Refuse d'écraser un rapport existant sans overwrite: true. " +
      "Ne modifie ni le suivi ni tasks.md.",
    input: {
      type: "object",
      properties: {
        change: { type: "string", description: "identifiant exact du change OpenSpec" },
        overwrite: { type: "boolean", description: "écraser le rapport existant" },
      },
      required: ["change"],
      additionalProperties: false,
    },
    async execute(input) {
      const off = inactive(deps)
      if (off) return text(off)

      const change = optionalString(input, "change") ?? failure("argument « change » requis")
      const resolved = resolveTarget(deps.directory, change, undefined, deps.readFile)
      if (!resolved.ok) {
        return text(`report refusé : ${resolved.message}\nSuivis disponibles : ${resolved.candidates.join(", ")}`)
      }
      const { target } = resolved
      const out = join("docs", `rapport-${change}.html`)

      if (existsSync(join(deps.directory, out)) && optionalBoolean(input, "overwrite") !== true) {
        return text(`${out} existe déjà — passer overwrite: true pour le remplacer.`)
      }

      const html = renderReport({
        change,
        title: changeTitle(deps.directory, change, deps.readFile),
        project: deps.config.projectName,
        file: target.file,
        tasksFile: target.tasksFile,
        tasks: target.tasks,
        generated: new Date().toISOString().slice(0, 10),
      })

      const absolute = join(deps.directory, out)
      mkdirSync(dirname(absolute), { recursive: true })
      writeFileSync(absolute, html, "utf-8")

      const done = target.tasks.filter((task) => task.status === "done").length
      const ecarts = target.tasks.filter((task) => task.status === "blocked").length
      return text(
        `${out} écrit (${target.tasks.length} tâches, ${done} terminées, ${ecarts} bloquée(s)) — ` +
          `état lu : ${target.stateFile}`,
      )
    },
  })
}
