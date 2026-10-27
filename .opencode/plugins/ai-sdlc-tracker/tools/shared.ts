/**
 * Dépendances communes des outils : configuration, accès disque, exécution des
 * scripts. Les outils ne construisent jamais un chemin absolu eux-mêmes et
 * n'exécutent jamais un script autrement que par `deps.runScript` (injectable
 * en test).
 */
import { readFileSync } from "node:fs"
import { join } from "node:path"
import {
  KILL_SWITCH,
  detectScope,
  gitRunner,
  loadEvidencePattern,
  pythonRunner,
  resolveConfig,
  type TrackerConfig,
} from "../core.ts"
import type { RunScript, ScriptResult, ToolDef, TrackerContext } from "../types.ts"

export const NAMESPACE = "sdlc"

export type Deps = {
  ctx: TrackerContext
  directory: string
  config: TrackerConfig
  runScript: RunScript
  runGit: (args: string[], cwd: string) => Promise<ScriptResult>
  readFile: (rel: string) => string
}

export function makeDeps(
  ctx: TrackerContext,
  overrides: Partial<Omit<Deps, "ctx">> = {},
  env: Record<string, string | undefined> = process.env as Record<string, string | undefined>,
): Deps {
  const directory = ctx.location.directory
  const config = resolveConfig(ctx.options, env, directory)
  return {
    ctx,
    directory,
    config,
    runScript: pythonRunner(config),
    runGit: gitRunner(config),
    readFile: (rel: string) => readFileSync(join(directory, rel), "utf-8"),
    ...overrides,
  }
}

/** Définition d'outil : namespace `sdlc`, utilisable en Code Mode. */
export function sdlcTool(definition: ToolDef): ToolDef {
  return { ...definition, options: { namespace: NAMESPACE, codemode: true, ...definition.options } }
}

export function failure(message: string): never {
  throw new Error(message)
}

/**
 * Le plugin doit-il rester spectateur ? Renvoie le message à afficher, ou
 * `undefined` si le plugin agit. En mode strict, l'inactivité est une erreur de
 * configuration au lieu d'un silence.
 */
export function inactive(deps: Deps): string | undefined {
  if (deps.config.killed) {
    return `[ai-sdlc-tracker] inactif : interrupteur d'urgence (${KILL_SWITCH}=off)`
  }
  if (!deps.config.enabled) return "[ai-sdlc-tracker] inactif : désactivé par configuration (enabled: false)"

  const scope = detectScope(deps.directory)
  if (scope.scope === "tracked") return undefined
  if (deps.config.strict) {
    failure(
      `[ai-sdlc-tracker] mode strict et dépôt non reconnu : ${scope.message}. ` +
        `Configurer checkScript/scriptsDir, ou passer strict: false.`,
    )
  }
  return `[ai-sdlc-tracker] ${scope.message}`
}

export function requireString(input: unknown, key: string): string {
  const value = (input as Record<string, unknown> | undefined)?.[key]
  if (typeof value === "string" && value.trim() !== "") return value.trim()
  failure(`argument « ${key} » requis (chaîne non vide)`)
}

export function optionalString(input: unknown, key: string): string | undefined {
  const value = (input as Record<string, unknown> | undefined)?.[key]
  return typeof value === "string" && value.trim() !== "" ? value.trim() : undefined
}

export function optionalBoolean(input: unknown, key: string): boolean | undefined {
  const value = (input as Record<string, unknown> | undefined)?.[key]
  return typeof value === "boolean" ? value : undefined
}

export function optionalStringArray(input: unknown, key: string): string[] | undefined {
  const value = (input as Record<string, unknown> | undefined)?.[key]
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string")
  return undefined
}

/** Motif de preuve du dépôt (celui de `scripts/check_sync.py`). */
export function evidenceFor(deps: Deps) {
  return loadEvidencePattern(join(deps.directory, deps.config.checkScript))
}

export function text(content: string): { content: string } {
  return { content }
}

/** Réponse d'outil à partir d'un appel de script : la sortie n'est pas reformulée. */
export function scriptText(label: string, result: { code: number; stdout: string; stderr: string }): string {
  const output = `${result.stdout}${result.stderr}`.trim()
  const status = result.code === 0 ? "OK" : `échec (code ${result.code})`
  return `${label} — ${status}\n${output}`
}
