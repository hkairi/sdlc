/**
 * Isolation des hooks.
 *
 * Un refus de gate est un résultat attendu : il doit atteindre l'appelant.
 * Toute autre erreur est un défaut interne : elle est journalisée et avalée.
 *
 * Pourquoi : pendant le développement, un import manquant dans un hook a fait
 * échouer un appel `edit`. Un outil de contrôle ne doit jamais empêcher de
 * travailler quand il est lui-même en panne — c'est le contraire de son rôle.
 */

/** Refus volontaire d'un gate : le seul cas où une erreur doit remonter. */
export class BlockError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "BlockError"
  }
}

export function isBlockError(error: unknown): boolean {
  return error instanceof BlockError || (error as { name?: string } | undefined)?.name === "BlockError"
}

/** Une ligne de journal, avec la première ligne de pile quand elle existe. */
export function logHookFailure(name: string, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error)
  const frame = error instanceof Error && error.stack ? error.stack.split("\n")[1]?.trim() : ""
  console.warn(
    `[ai-sdlc-tracker] contrôle « ${name} » en échec (ignoré, session préservée) : ${message}` +
      (frame ? ` — ${frame}` : ""),
  )
}

/**
 * Enveloppe un callback de hook : relance un `BlockError`, avale le reste.
 * Le callback peut être synchrone ou asynchrone ; la garde renvoie toujours une
 * promesse résolue (sauf refus).
 */
export function guarded<Event>(
  name: string,
  fn: (event: Event) => unknown,
): (event: Event) => Promise<void> {
  return async (event: Event) => {
    try {
      await fn(event)
    } catch (error) {
      if (isBlockError(error)) throw error
      logHookFailure(name, error)
    }
  }
}
