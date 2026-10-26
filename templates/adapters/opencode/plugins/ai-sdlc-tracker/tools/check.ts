/**
 * `sdlc_check` — contrôle de synchronisation, délégué au script du dépôt.
 *
 * Le verdict n'est jamais reformulé : c'est celui de `scripts/check_sync.py`,
 * donc celui du hook git et de la CI. Trois modes exclusifs : un change, tous
 * les changes ouverts (`all`), ou les chemins touchés (`paths`).
 */
import { checkScriptPath, resolveTarget } from "../core.ts"
import {
  inactive,
  optionalBoolean,
  optionalString,
  optionalStringArray,
  sdlcTool,
  scriptText,
  text,
} from "./shared.ts"
import type { Deps } from "./shared.ts"
import type { ToolDef } from "../types.ts"

export function defineCheck(deps: Deps): ToolDef {
  return sdlcTool({
    name: "check",
    description:
      "Contrôle que docs/suivi/state.json et openspec/changes/<change>/tasks.md sont synchrones. " +
      "Même verdict que le hook git et la CI. À lancer avant un commit ou une clôture. " +
      "Modes exclusifs : « change » (un change), all: true (tous les changes ouverts), « paths » (chemins touchés).",
    input: {
      type: "object",
      properties: {
        change: { type: "string", description: "identifiant exact du change OpenSpec" },
        all: { type: "boolean", description: "contrôler tous les changes ouverts" },
        paths: { type: "array", items: { type: "string" }, description: "chemins touchés (mode des gates)" },
        requireEvidence: { type: "boolean", description: "exiger une preuve chiffrée pour chaque tâche done" },
      },
      additionalProperties: false,
    },
    async execute(input) {
      const off = inactive(deps)
      if (off) return text(off)

      const change = optionalString(input, "change")
      const all = optionalBoolean(input, "all") === true
      const paths = optionalStringArray(input, "paths")
      const modes = [
        change ? "change" : "",
        all ? "all" : "",
        paths && paths.length > 0 ? "paths" : "",
      ].filter(Boolean)
      if (modes.length === 0) return text("préciser un mode : change « <id> », all: true, ou paths: [ … ]")
      if (modes.length > 1) return text(`un seul mode à la fois (reçu : ${modes.join(" + ")})`)

      const script = checkScriptPath(deps.directory, deps.config).replace(`${deps.directory}/`, "")
      const args: string[] = []
      let label = ""

      if (change) {
        const target = resolveTarget(deps.directory, change, undefined, deps.readFile)
        if (!target.ok) {
          return text(`check refusé : ${target.message}\nSuivis disponibles : ${target.candidates.join(", ")}`)
        }
        args.push("--state", target.target.stateFile, "--tasks", target.target.tasksFile)
        label = `${target.target.stateFile} ↔ ${target.target.tasksFile}`
      } else if (all) {
        args.push("--all")
        label = "tous les changes ouverts"
      } else {
        args.push("--paths", ...(paths ?? []))
        label = `chemins touchés (${(paths ?? []).length})`
      }
      if (optionalBoolean(input, "requireEvidence") === true) args.push("--require-evidence")

      const result = await deps.runScript(script, args, deps.directory)
      return text(scriptText(`check — ${label}`, result))
    },
  })
}
