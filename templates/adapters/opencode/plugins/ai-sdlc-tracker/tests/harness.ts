/**
 * Faux contexte de plugin OpenCode.
 *
 * Pourquoi : la logique du plugin (règles de blocage, résolution de cible, outils,
 * hooks) doit être exerçable sans lancer OpenCode. Ce harnais capture ce que
 * `setup(ctx)` enregistre — outils, hooks, abonnements d'événements — et laisse
 * les tests appeler ces enregistrements directement, avec un exécuteur de
 * scripts simulé (aucune écriture réelle, aucun sous-processus).
 */

import type { Editor, HookEvent, ScriptResult, ToolDef, TrackerContext } from "../types.ts"

export type HarnessInit = {
  /** Racine du dépôt vue par le plugin. */
  directory?: string
  /** Options passées à `plugins[]` (config du dépôt). */
  options?: Record<string, unknown>
  /** Variables d'environnement visibles par le plugin (kill switch). */
  env?: Record<string, string | undefined>
  /** Événements du serveur à distribuer aux abonnés. */
  events?: HookEvent[]
  /** Réponse simulée des scripts : (script, args) → code/sortie. */
  respond?: (script: string, args: string[]) => ScriptResult
  /** Fichiers disponibles sur le disque simulé : chemin → contenu. */
  files?: Record<string, string>
}

/** Nom effectif d'un outil, comme OpenCode le compose (namespace_name). */
export function effectiveToolName(namespace: string | undefined, name: string): string {
  const raw = namespace ? `${namespace}_${name}` : name
  return raw.replace(/[.\s-]+/g, "_").replace(/[^A-Za-z0-9_]/g, "_")
}

export function createHarness(init: HarnessInit = {}) {
  const files = { ...(init.files ?? {}) }
  const tools = new Map<string, ToolDef>()
  const hooks: Record<string, ((event: HookEvent) => unknown)[]> = {}
  const synthetic: string[] = []
  const prompts: string[] = []
  const calls: { script: string; args: string[]; cwd: string }[] = []
  let currentNamespace: string | undefined
  let aborted = false

  const respond: (script: string, args: string[]) => ScriptResult =
    init.respond ?? (() => ({ code: 0, stdout: "", stderr: "" }))

  const editor: Editor = {
    add(tool) {
      tools.set(effectiveToolName(tool.options?.namespace ?? currentNamespace, tool.name), tool)
    },
    update(id, update) {
      const tool = tools.get(id)
      if (tool) update(tool)
    },
    remove(id) {
      tools.delete(id)
    },
    get(id) {
      return tools.get(id)
    },
    list() {
      return [...tools.values()]
    },
    namespace(ns) {
      currentNamespace = ns.name
    },
  }

  const registration = { dispose: async () => {} }

  const ctx: TrackerContext = {
    location: { directory: init.directory ?? process.cwd(), project: { id: "test", directory: init.directory ?? process.cwd() } },
    options: init.options ?? {},
    tool: {
      async transform(cb: (editor: Editor) => void) {
        cb(editor)
        return registration
      },
      async hook(name: string, cb: (event: HookEvent) => unknown) {
        ;(hooks[name] ||= []).push(cb)
        return registration
      },
      async list() {
        return [...tools.entries()].map(([id, tool]) => ({ ...tool, id }))
      },
    },
    session: {
      async synthetic(input: { sessionID?: string; text: string }) {
        synthetic.push(input.text)
      },
      async prompt(input: { sessionID?: string; text: string }) {
        prompts.push(input.text)
      },
    },
    event: {
      async *subscribe(options?: { signal?: AbortSignal }) {
        for (const event of init.events ?? []) {
          if (options?.signal?.aborted || aborted) return
          yield event
        }
      },
    },
  }

  return {
    ctx,
    /** Environnement simulé (kill switch, chemins). */
    env: { ...(init.env ?? {}) },
    /** Fichiers du disque simulé. */
    files,
    /** Outils enregistrés, indexés par nom effectif. */
    tools,
    /** Hooks enregistrés, indexés par nom de hook. */
    hooks,
    /** Messages synthétiques déposés (`session.synthetic`). */
    synthetic,
    /** Prompts envoyés (`session.prompt`) — ne doit jamais être utilisé pour alerter. */
    prompts,
    /** Appels de scripts capturés (script, arguments, cwd). */
    calls,
    /** Exécuteur de script à injecter dans le plugin. */
    runScript: async (script: string, args: string[], cwd: string): Promise<ScriptResult> => {
      calls.push({ script, args, cwd })
      return respond(script, args)
    },
    /** Appelle un hook et renvoie ce que le premier callback exploitable renvoie. */
    async fireHook(name: string, event: HookEvent) {
      const results: unknown[] = []
      for (const cb of hooks[name] ?? []) results.push(await cb(event))
      return results
    },
    /** Appelle un outil par son nom effectif. */
    async callTool(name: string, input: unknown, context?: unknown) {
      const tool = tools.get(name)
      if (!tool?.execute) throw new Error(`outil inconnu : ${name}`)
      return tool.execute(input, context)
    },
    /** Simule l'abandon des abonnements (cleanup du plugin). */
    abort() {
      aborted = true
    },
  }
}

export type Harness = ReturnType<typeof createHarness>
