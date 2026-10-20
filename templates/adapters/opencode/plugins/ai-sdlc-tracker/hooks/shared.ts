/**
 * Règles communes des hooks : reconnaître une commande, reconnaître un chemin
 * suivi, produire le verdict de synchronisation.
 *
 * Les hooks ne bloquent que par exception, et un blocage porte toujours le
 * détail des écarts plus la commande de correction.
 */
import { join } from "node:path"
import { checkScriptPath } from "../core.ts"
import type { Deps } from "../tools/shared.ts"
import type { HookEvent } from "../types.ts"

/**
 * Un chemin qui porte l'état du suivi : `tasks.md` d'un change (y compris
 * archivé) ou un fichier de suivi. Écrire `proposal.md`, `design.md` ou un delta
 * de spec ne déclenche rien (constaté le 2026-10-19 : le filtre trop large
 * produisait « sync OK : 0 tâche(s) » à chaque rédaction).
 */
export const TRACKED_PATH =
  /(^|\/)(openspec\/changes\/(?:archive\/\d{4}-\d{2}-\d{2}-)?[^/]+\/tasks\.md|docs\/suivi-[^/]+\.html)$/

/** Supprime les segments entre guillemets : `rg "git commit" docs/` n'est pas un commit. */
export function stripQuoted(command: string): string {
  return command.replace(/'[^']*'|"[^"]*"/g, " ")
}

/** La commande est-elle un `git commit` réellement exécuté ? */
export function isGitCommit(command: string): boolean {
  return /\bgit(?:\s+-{1,2}\S+(?:\s+\S+)?|\s+-C\s+\S+)*\s+commit\b/.test(stripQuoted(command))
}

/** La commande est-elle un `openspec validate <id>` (hors `--all`) ? */
export function openspecValidateChange(command: string): string | undefined {
  const plain = stripQuoted(command)
  if (!/\bopenspec\s+validate\b/.test(plain)) return undefined
  if (/\s--all\b/.test(plain)) return undefined
  const tokens = plain.split(/\s+/)
  const at = tokens.indexOf("validate")
  if (at < 0) return undefined
  return tokens.slice(at + 1).find((token) => !token.startsWith("-"))
}

/** Identifiant de change déduit d'un chemin suivi (`docs/suivi-x.html`, `…/tasks.md`). */
export function changeOfPath(path: string): string | undefined {
  const suivi = /^docs\/suivi-(.+)\.html$/.exec(path)
  if (suivi && suivi[1] !== "multi") return suivi[1]
  const tasks = /^openspec\/changes\/(?:archive\/\d{4}-\d{2}-\d{2}-)?([^/]+)\/tasks\.md$/.exec(path)
  return tasks?.[1]
}

/** Écritures d'un outil d'édition, quelles que soient les clés du harnais. */
export function writtenPaths(input: unknown): string[] {
  const record = (input ?? {}) as Record<string, unknown>
  const out: string[] = []
  for (const key of ["filePath", "path", "file"]) {
    const value = record[key]
    if (typeof value === "string") out.push(value)
  }
  return out
}

export function commandOf(input: unknown): string {
  const record = (input ?? {}) as Record<string, unknown>
  return typeof record.command === "string" ? record.command : ""
}

export type Verdict = { ok: boolean; message: string; timedOut?: boolean }

/**
 * Chemins ramenés dans le dépôt. Les outils d'écriture d'OpenCode fournissent des
 * chemins ABSOLUS : `check_sync.py --paths` ne reconnaît que des chemins relatifs
 * au dépôt, sinon il ne contrôle rien et répond « rien à contrôler » (constaté en
 * session le 2026-10-19 — un faux « synchrone »).
 */
export function relativize(directory: string, paths: string[]): string[] {
  const root = directory.endsWith("/") ? directory : `${directory}/`
  return paths
    .map((path) => path.replace(/^\.\//, ""))
    .map((path) => (path.startsWith(root) ? path.slice(root.length) : path))
    .filter((path) => !path.startsWith("/") && !path.startsWith(".."))
}

/** Verdict de synchronisation pour un ensemble de chemins (ceux du contrôle). */
export async function verdictFor(deps: Deps, paths: string[], requireEvidence = false): Promise<Verdict> {
  const script = checkScriptPath(deps.directory, deps.config).replace(`${deps.directory}/`, "")
  const relative = relativize(deps.directory, paths)
  const args = ["--paths", ...relative, ...(requireEvidence ? ["--require-evidence"] : [])]
  const result = await deps.runScript(script, args, deps.directory)
  const message = `${result.stdout}${result.stderr}`.trim()
  return {
    ok: result.code === 0,
    message: message || `check_sync.py (code ${result.code})`,
    timedOut: result.code === 124,
  }
}

/** Chemins à contrôler pour un commit : indexés d'abord, sinon l'arbre de travail. */
export async function commitPaths(deps: Deps): Promise<string[]> {
  const staged = await deps.runGit(["diff", "--cached", "--name-only"], deps.directory)
  const stagedPaths = staged.stdout.split("\n").map((line) => line.trim()).filter(Boolean)
  if (stagedPaths.length > 0) return stagedPaths

  // `-uall` force git à lister les fichiers non suivis un par un (sans lui, un
  // répertoire entièrement nouveau apparaît comme `?? docs/` et le contrôle ne voit
  // aucun change). Constaté en test d'intégration le 2026-10-19.
  const status = await deps.runGit(["status", "--porcelain", "-uall"], deps.directory)
  return status.stdout
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const raw = line.slice(3).trim()
      const renamed = raw.split(" -> ").pop() ?? raw
      return renamed.replace(/^"|"$/g, "")
    })
}

export function correctionHint(taskId = "<tâche>"): string {
  return (
    `Corriger tout de suite, une tâche à la fois : sdlc_track { change, task: "${taskId}", status: "done", ` +
    `note: "Fait : … ; vérifié : <chiffres>" }.`
  )
}

/** Ajoute un texte à la sortie visible de l'outil, sans écraser l'existant. */
export function appendToResult(event: HookEvent, text: string): void {
  const result = event.result as { content?: unknown } | undefined
  if (event.output !== undefined) {
    event.output = `${String(event.output)}${event.output ? "\n" : ""}${text}`
    return
  }
  if (result && typeof result.content === "string") {
    result.content = `${result.content}\n${text}`
    return
  }
  if (result && Array.isArray(result.content)) {
    result.content.push({ type: "text", text })
    return
  }
  event.result = { content: text }
}

export function relative(directory: string, path: string): string {
  const absolute = join(directory, path)
  return absolute.startsWith(directory) ? absolute.slice(directory.length + 1) : path
}