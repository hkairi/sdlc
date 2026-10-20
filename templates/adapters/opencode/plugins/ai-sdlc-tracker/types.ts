/**
 * Types partagés du plugin — volontairement minimaux et structurels.
 *
 * Ils décrivent la partie du contexte OpenCode que le plugin utilise réellement.
 * Le contexte réel d'OpenCode les satisfait ; le faux contexte des tests
 * (`tests/harness.ts`) s'y conforme aussi, sans import circulaire.
 */

export type ScriptResult = { code: number; stdout: string; stderr: string }

/** Exécuteur de scripts, injectable (le vrai spawn vit dans `core.ts`). */
export type RunScript = (script: string, args: string[], cwd: string) => Promise<ScriptResult>

export type ToolDef = {
  name: string
  description?: string
  input?: unknown
  options?: { namespace?: string; codemode?: boolean }
  execute?: (input: unknown, context?: unknown) => Promise<unknown>
}

export type HookEvent = Record<string, unknown>

export type Editor = {
  add(tool: ToolDef): void
  update(id: string, update: (tool: ToolDef) => void): void
  remove(id: string): void
  get(id: string): ToolDef | undefined
  list(): ToolDef[]
  namespace(ns: { name: string; description: string }): void
}

export type TrackerContext = {
  location: { directory: string; project?: { id?: string; directory?: string } }
  options: Record<string, unknown>
  tool: {
    transform(cb: (editor: Editor) => void): Promise<unknown>
    hook(name: string, cb: (event: HookEvent) => unknown): Promise<unknown>
    list?(): Promise<unknown[]>
  }
  session: {
    synthetic(input: { sessionID?: string; text: string }): Promise<unknown>
    prompt?(input: { sessionID?: string; text: string }): Promise<unknown>
  }
  event: {
    subscribe(options?: { signal?: AbortSignal }): AsyncIterable<HookEvent>
  }
}
