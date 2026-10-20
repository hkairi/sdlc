/**
 * `sdlc_doctor` — contrôle de santé, en lecture seule.
 *
 * Pourquoi un outil dédié : la panne la plus coûteuse du plugin n'est pas un
 * mauvais verdict, c'est un plugin présent mais inerte (le cas `suivi-sync.ts`).
 * Le doctor répond en une commande : quelles règles s'appliquent ici, avec quoi,
 * et qu'est-ce qui manque.
 */
import { existsSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { detectScope, scriptPath } from "../core.ts"
import { inactive, sdlcTool, text } from "./shared.ts"
import type { Deps } from "./shared.ts"
import type { ToolDef } from "../types.ts"

export const REQUIRED_SCRIPTS = [
  "track.py",
  "track_multi.py",
  "track_phase.py",
  "generate.py",
  "generate_multi.py",
  "generate_from_openspec.py",
  "phases.py",
  "sourcedocs.py",
]

export const REQUIRED_ASSETS = ["template.html", "template-multi.html", "manifest-example.json"]

function pluginVersion(deps: Deps): string {
  try {
    const pkg = JSON.parse(deps.readFile(join(".opencode", "plugins", "ai-sdlc-tracker", "package.json"))) as {
      version?: string
    }
    return pkg.version ?? "inconnue"
  } catch {
    return "inconnue (package.json illisible)"
  }
}

export function defineDoctor(deps: Deps): ToolDef {
  return sdlcTool({
    name: "doctor",
    description:
      "Contrôle de santé en lecture seule : version du plugin, périmètre détecté, configuration effective, " +
      "scripts et gabarits présents, hook git installé, dette gelée, binaire Python. Conclut par « prêt » " +
      "ou « à corriger » avec les actions à mener. N'écrit aucun fichier et ne bloque rien.",
    input: { type: "object", properties: {}, additionalProperties: false },
    async execute() {
      const lines: string[] = []
      const actions: string[] = []
      const config = deps.config

      lines.push(`version du plugin : ${pluginVersion(deps)}`)
      lines.push(`config active : ${config.killed ? "coupée par AI_SDLC_TRACKER=off" : config.enabled ? "oui" : "non (enabled: false)"}`)

      const scope = detectScope(deps.directory)
      lines.push(`périmètre : ${scope.scope} — ${scope.message}`)
      if (scope.scope === "none") {
        actions.push("aucun change OpenSpec ni suivi : le plugin est inactif ici (fail-open attendu)")
      }

      const checkPath = join(deps.directory, config.checkScript)
      lines.push(`script de contrôle : ${config.checkScript} — ${existsSync(checkPath) ? "présent" : "ABSENT"}`)
      if (!existsSync(checkPath)) actions.push(`restaurer ${config.checkScript} (ou configurer checkScript)`)

      const missingScripts = REQUIRED_SCRIPTS.filter((name) => !existsSync(join(deps.directory, scriptPath(config, name))))
      const missingAssets = REQUIRED_ASSETS.filter((name) => !existsSync(join(deps.directory, config.scriptsDir, "assets", name)))
      const vendorOk = missingScripts.length === 0 && missingAssets.length === 0
      lines.push(`vendorisation (${config.scriptsDir}) : ${vendorOk ? "complète" : `incomplète (${missingScripts.length + missingAssets.length} manquant(s))`}`)
      if (!vendorOk) {
        actions.push(`vendoriser : python3 ${config.scriptsDir}/sync_from_skill.py --write`)
        if (missingScripts.length > 0) lines.push(`  scripts manquants : ${missingScripts.join(", ")}`)
        if (missingAssets.length > 0) lines.push(`  gabarits manquants : ${missingAssets.join(", ")}`)
      }

      lines.push(`python : ${config.pythonBin}`)
      lines.push(`délai des commandes : ${config.commandTimeoutMs} ms`)

      const baselinePath = join(deps.directory, config.scriptsDir, "baseline.json")
      if (existsSync(baselinePath)) {
        try {
          const baseline = JSON.parse(readFileSync(baselinePath, "utf-8")) as {
            generated?: string
            drifts?: string[]
            unproven?: Record<string, string[]>
          }
          const drifts = baseline.drifts?.length ?? 0
          const unproven = Object.values(baseline.unproven ?? {}).reduce((total, tasks) => total + tasks.length, 0)
          lines.push(
            `baseline : ${baseline.generated ?? "date inconnue"} ` +
              `(${drifts} dérive(s) connue(s), ${unproven} tâche(s) sans preuve)`,
          )
        } catch {
          lines.push("baseline : illisible")
          actions.push(`régénérer ${config.scriptsDir}/baseline.json`)
        }
      } else {
        lines.push("baseline : absente (tout problème existant sera signalé comme nouveau)")
      }

      const hooks = await deps.runGit(["config", "core.hooksPath"], deps.directory)
      const hookPath = hooks.stdout.trim()
      if (hooks.code !== 0 || hookPath === "") {
        lines.push("hook git : NON installé")
        actions.push("installer le hook git : git config core.hooksPath .githooks")
      } else {
        lines.push(`hook git : ${hookPath}`)
      }

      const configErrors = []
      if (!Number.isFinite(config.commandTimeoutMs) || config.commandTimeoutMs <= 0) configErrors.push("commandTimeoutMs")
      if (config.pythonBin === "") configErrors.push("pythonBin")
      if (configErrors.length > 0) actions.push(`corriger la configuration : ${configErrors.join(", ")}`)

      const off = inactive(deps)
      if (off) lines.push(`gates : ${off}`)

      const verdict = actions.length === 0 ? "prêt" : "à corriger"
      const actionsBlock = actions.length > 0 ? ["", "actions :", ...actions.map((a) => `  - ${a}`)] : []
      return text([`sdlc_doctor — ${verdict}`, ...lines, ...actionsBlock].join("\n"))
    },
  })
}
