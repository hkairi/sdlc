/**
 * Cœur logique du plugin — pur, sans dépendance à OpenCode, testable seul.
 *
 * Trois responsabilités, et rien d'autre :
 *  1. décider si le plugin s'applique à ce dépôt (`resolveConfig`, `detectScope`) ;
 *  2. trouver ce qu'une tâche désigne vraiment (`resolveTarget`, mono ou multi) ;
 *  3. porter les règles de blocage (`canStartTask`) et l'alignement sur le script
 *     de contrôle (`loadEvidencePattern`).
 *
 * Aucun chemin en dur : tout part de `directory` (la racine du dépôt vue par
 * OpenCode) et de la configuration.
 */
import { existsSync, readdirSync, readFileSync } from "node:fs"
import { basename, join, resolve } from "node:path"
import { spawn } from "node:child_process"
import type { RunScript, ScriptResult } from "./types.ts"

export const KILL_SWITCH = "AI_SDLC_TRACKER"

export type TrackerConfig = {
  enabled: boolean
  autoGenerate: boolean
  blockCommit: boolean
  blockNextTask: boolean
  requireEvidence: boolean
  alertOnIdle: boolean
  strict: boolean
  projectName: string
  /** Script de contrôle de synchronisation (chemin relatif au dépôt). */
  checkScript: string
  /** Racine de la vendorisation : `<scriptsDir>/scripts/*.py`, `<scriptsDir>/assets/*`. */
  scriptsDir: string
  /** Binaire Python (défaut : `python3`, ou `python` sous Windows). */
  pythonBin: string
  /** Délai maximal d'une commande externe, en millisecondes. */
  commandTimeoutMs: number
  /** Interrupteur d'urgence actif (`AI_SDLC_TRACKER=off`) : plus aucun blocage. */
  killed: boolean
}

export const DEFAULT_CONFIG: Omit<TrackerConfig, "killed"> = {
  enabled: true,
  autoGenerate: true,
  blockCommit: true,
  blockNextTask: true,
  requireEvidence: true,
  alertOnIdle: false,
  strict: false,
  projectName: "",
  checkScript: "scripts/check_sync.py",
  scriptsDir: "scripts/suivi",
  pythonBin: "",
  commandTimeoutMs: 10_000,
}

function flag(options: Record<string, unknown>, key: string, fallback: boolean): boolean {
  const value = options[key]
  return typeof value === "boolean" ? value : fallback
}

function text(options: Record<string, unknown>, key: string, fallback: string): string {
  const value = options[key]
  return typeof value === "string" && value.trim() !== "" ? value.trim() : fallback
}

function positiveNumber(options: Record<string, unknown>, key: string, fallback: number): number {
  const value = options[key]
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? Math.floor(value) : fallback
}

export function resolveConfig(
  options: Record<string, unknown> = {},
  env: Record<string, string | undefined> = {},
  directory = "",
): TrackerConfig {
  const kill = (env[KILL_SWITCH] ?? "").toLowerCase()
  const killed = kill === "off" || kill === "0" || kill === "false"
  const derivedProject = directory ? basename(resolve(directory)) : "projet"
  const platformPython = typeof process !== "undefined" && process.platform === "win32" ? "python" : "python3"
  return {
    enabled: flag(options, "enabled", DEFAULT_CONFIG.enabled),
    autoGenerate: flag(options, "autoGenerate", DEFAULT_CONFIG.autoGenerate),
    blockCommit: flag(options, "blockCommit", DEFAULT_CONFIG.blockCommit),
    blockNextTask: flag(options, "blockNextTask", DEFAULT_CONFIG.blockNextTask),
    requireEvidence: flag(options, "requireEvidence", DEFAULT_CONFIG.requireEvidence),
    alertOnIdle: flag(options, "alertOnIdle", DEFAULT_CONFIG.alertOnIdle),
    strict: flag(options, "strict", DEFAULT_CONFIG.strict),
    projectName: text(options, "projectName", derivedProject),
    checkScript: text(options, "checkScript", DEFAULT_CONFIG.checkScript),
    scriptsDir: text(options, "scriptsDir", DEFAULT_CONFIG.scriptsDir),
    pythonBin: text(options, "pythonBin", platformPython),
    commandTimeoutMs: positiveNumber(options, "commandTimeoutMs", DEFAULT_CONFIG.commandTimeoutMs),
    killed,
  }
}

/** Un gate est-il actif ? (config activée et interrupteur d'urgence non déclenché) */
export function gatesEnabled(config: TrackerConfig): boolean {
  return config.enabled && !config.killed
}

export type Scope = { scope: "tracked" | "none"; message: string }

/** Le dépôt a-t-il des changes OpenSpec ou des suivis ? Sinon, le plugin est inactif. */
export function detectScope(directory: string): Scope {
  const changes = listOpenChanges(directory)
  const suivis = listSuivis(directory)
  if (changes.length > 0 || suivis.length > 0) {
    return {
      scope: "tracked",
      message: `${changes.length} change(s) OpenSpec, ${suivis.length} suivi(s) dans docs/`,
    }
  }
  return { scope: "none", message: "outil inactif : aucun change OpenSpec ni suivi reconnu dans ce dépôt" }
}

export function listSuivis(directory: string): string[] {
  const docs = join(directory, "docs")
  if (!existsSync(docs)) return []
  return readdirSync(docs)
    .filter((name) => /^suivi-.*\.html$/.test(name))
    .map((name) => join("docs", name))
    .sort()
}

export function listOpenChanges(directory: string): { id: string; tasksFile: string }[] {
  const changes = join(directory, "openspec", "changes")
  if (!existsSync(changes)) return []
  const out: { id: string; tasksFile: string }[] = []
  for (const entry of readdirSync(changes, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === "archive") continue
    const tasks = join(changes, entry.name, "tasks.md")
    if (existsSync(tasks)) out.push({ id: entry.name, tasksFile: join("openspec", "changes", entry.name, "tasks.md") })
  }
  return out.sort((a, b) => a.id.localeCompare(b.id))
}

/** Chemin du `tasks.md` d'un change, y compris archivé (`archive/<date>-<id>/`). */
export function findTasksFile(directory: string, changeId: string): string | undefined {
  const direct = join("openspec", "changes", changeId, "tasks.md")
  if (existsSync(join(directory, direct))) return direct
  const archive = join(directory, "openspec", "changes", "archive")
  if (!existsSync(archive)) return undefined
  const match = readdirSync(archive).find(
    (name) => (name === changeId || name.endsWith(`-${changeId}`)) && existsSync(join(archive, name, "tasks.md")),
  )
  return match ? join("openspec", "changes", "archive", match, "tasks.md") : undefined
}

// ---------------------------------------------------------------------------
// Lecture de l'état : mono (HTML) et multi (bloc feature-data)
// ---------------------------------------------------------------------------

export type TaskState = {
  id: string
  lot: string
  status: string
  updated: string
  note: string
  title: string
}

function lotOf(id: string): string {
  return id.includes(".") ? id.split(".")[0] : id
}

/** Tâches d'un suivi mono : le HTML est la source de vérité de ce modèle. */
export function parseMonoTasks(html: string): TaskState[] {
  const tasks: TaskState[] = []
  const markers = [...html.matchAll(/<div class="task" data-id="([^"]+)"[^>]*>/g)]
  markers.forEach((marker, index) => {
    const start = marker.index ?? 0
    const end = index + 1 < markers.length ? (markers[index + 1].index ?? html.length) : html.length
    const block = html.slice(start, end)
    const attrs = marker[0]
    const status = /data-status="([^"]*)"/.exec(attrs)?.[1] ?? "todo"
    const updated = /data-updated="([^"]*)"/.exec(attrs)?.[1] ?? ""
    const rawNote = /<em class="note">([\s\S]*?)<\/em>/.exec(block)?.[1] ?? ""
    const title = /<h3>([\s\S]*?)<\/h3>/.exec(block)?.[1] ?? ""
    tasks.push({
      id: marker[1],
      lot: lotOf(marker[1]),
      status,
      updated,
      note: rawNote.replace(/<[^>]*>/g, "").trim(),
      title: title.replace(/<[^>]*>/g, "").trim(),
    })
  })
  return tasks
}

export type MultiFeature = {
  key: string
  change?: string
  tasksFile?: string
  tasks: TaskState[]
}

/** Features du suivi multi (bloc `feature-data`). */
export function parseMultiFeatures(html: string): MultiFeature[] {
  const match = /<script type="application\/json" id="feature-data">([\s\S]*?)<\/script>/.exec(html)
  if (!match) return []
  let data: unknown
  try {
    data = JSON.parse(match[1])
  } catch {
    return []
  }
  const features = (data as { features?: unknown[] }).features
  if (!Array.isArray(features)) return []
  return features.map((raw) => {
    const feature = raw as Record<string, unknown>
    const tasks = Array.isArray(feature.tasks) ? feature.tasks : []
    return {
      key: String(feature.id ?? ""),
      change: typeof feature.change === "string" ? feature.change : undefined,
      tasksFile: typeof feature.tasks_file === "string" ? feature.tasks_file : undefined,
      tasks: tasks.map((rawTask) => {
        const task = rawTask as Record<string, unknown>
        const id = String(task.id ?? "")
        return {
          id,
          lot: String(task.lot ?? lotOf(id)),
          status: String(task.status ?? "todo"),
          updated: String(task.updated ?? ""),
          note: String(task.note ?? "").replace(/<[^>]*>/g, "").trim(),
          title: String(task.title ?? "").replace(/<[^>]*>/g, "").trim(),
        }
      }),
    }
  })
}

export type Target = {
  kind: "mono" | "multi"
  /** Fichier de suivi à mettre à jour (relatif au dépôt). */
  file: string
  /** Clé de la feature, en multi uniquement (pour `track_multi.py`). */
  feature?: string
  tasksFile: string
  tasks: TaskState[]
}

export type TargetResult =
  | { ok: true; target: Target }
  | { ok: false; message: string; candidates: string[] }

/**
 * Résout la cible d'une tâche : suivi mono `docs/suivi-<id>.html`, sinon la
 * feature du suivi multi dont `change` ou `tasks_file` correspond. Un `file`
 * explicite force la cible. Le résultat nomme toujours le fichier retenu.
 */
export function resolveTarget(
  directory: string,
  changeId: string,
  overrideFile?: string,
  readFile: (path: string) => string = (path) => readFileSync(join(directory, path), "utf-8"),
): TargetResult {
  const monoFile = join("docs", `suivi-${changeId}.html`)
  const candidates = [...listSuivis(directory), ...listOpenChanges(directory).map((c) => c.tasksFile)]

  if (overrideFile) {
    const rel = overrideFile.replace(/^\.\//, "")
    if (!existsSync(join(directory, rel))) {
      return { ok: false, message: `fichier de suivi introuvable : ${rel}`, candidates }
    }
    const content = readFile(rel)
    if (/id="feature-data"/.test(content)) {
      const feature = parseMultiFeatures(content).find((f) => f.change === changeId)
      if (!feature) {
        return {
          ok: false,
          message: `${rel} ne référence pas le change ${changeId} (features : ${parseMultiFeatures(content).map((f) => f.key).join(", ") || "aucune"})`,
          candidates,
        }
      }
      return {
        ok: true,
        target: {
          kind: "multi",
          file: rel,
          feature: feature.key,
          tasksFile: feature.tasksFile ?? findTasksFile(directory, changeId) ?? "",
          tasks: feature.tasks,
        },
      }
    }
    return {
      ok: true,
      target: {
        kind: "mono",
        file: rel,
        tasksFile: findTasksFile(directory, changeId) ?? "",
        tasks: parseMonoTasks(content),
      },
    }
  }

  if (existsSync(join(directory, monoFile))) {
    return {
      ok: true,
      target: {
        kind: "mono",
        file: monoFile,
        tasksFile: findTasksFile(directory, changeId) ?? "",
        tasks: parseMonoTasks(readFile(monoFile)),
      },
    }
  }

  const multiFile = join("docs", "suivi-multi.html")
  if (existsSync(join(directory, multiFile))) {
    const features = parseMultiFeatures(readFile(multiFile))
    const feature = features.find(
      (f) => f.change === changeId || (f.tasksFile ?? "").includes(`/${changeId}/`),
    )
    if (feature) {
      return {
        ok: true,
        target: {
          kind: "multi",
          file: multiFile,
          feature: feature.key,
          tasksFile: feature.tasksFile ?? findTasksFile(directory, changeId) ?? "",
          tasks: feature.tasks,
        },
      }
    }
  }

  return {
    ok: false,
    message:
      `aucun suivi pour le change ${changeId} : ni docs/suivi-${changeId}.html, ni feature correspondante dans docs/suivi-multi.html. ` +
      `Générer le suivi (sdlc_generate) ou vérifier l'identifiant.`,
    candidates,
  }
}

// ---------------------------------------------------------------------------
// Règle de preuve : alignée sur EVIDENCE_RE du script de contrôle
// ---------------------------------------------------------------------------

export const FALLBACK_EVIDENCE_PATTERNS = [
  "make test",
  "go test",
  "rspec",
  "bin/rails",
  "exit\\s*=\\s*0",
  "\\d+\\s*(examples?|échec|échecs|failures?|offenses?|scénarios?|critères?|tests?)",
  "\\d+\\s*/\\s*\\d+",
  "vérifié",
  "explain",
]

export type EvidencePattern = { regex: RegExp; source: "script" | "fallback"; pattern: string }

/** Extrait le motif de preuve du script de contrôle : une seule vérité pour les deux. */
export function loadEvidencePattern(checkScriptPath: string | undefined): EvidencePattern {
  const fallback = {
    regex: new RegExp(FALLBACK_EVIDENCE_PATTERNS.join("|"), "i"),
    source: "fallback" as const,
    pattern: FALLBACK_EVIDENCE_PATTERNS.join("|"),
  }
  if (!checkScriptPath || !existsSync(checkScriptPath)) return fallback

  const source = readFileSync(checkScriptPath, "utf-8")
  const block = /EVIDENCE_RE\s*=\s*re\.compile\(([\s\S]*?)\n\)/.exec(source)?.[1]
  if (!block) return fallback

  const literals = [...block.matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((m) => m[1])
  if (literals.length === 0) return fallback

  try {
    // Les littéraux du script sont concaténés par Python (chaînes adjacentes) :
    // les joindre avec « | » insérerait des alternatives vides (le motif
    // matcherait alors n'importe quoi — attrapé par le test d'alignement).
    const pattern = literals.join("")
    return { regex: new RegExp(pattern, "i"), source: "script", pattern }
  } catch {
    return fallback
  }
}

export function noteHasEvidence(note: string, evidence: EvidencePattern): boolean {
  return evidence.regex.test(note)
}

// ---------------------------------------------------------------------------
// Une seule tâche en cours par lot
// ---------------------------------------------------------------------------

export type StartDecision = { ok: true } | { ok: false; message: string; blocking: TaskState }

export function canStartTask(
  tasks: TaskState[],
  taskId: string,
  options: { force?: boolean; reason?: string } = {},
): StartDecision {
  const lot = lotOf(taskId)
  const blocking = tasks.find(
    (task) => task.id !== taskId && task.lot === lot && task.status === "doing" && task.note.trim() === "",
  )
  if (!blocking) return { ok: true }

  if (options.force && (options.reason ?? "").trim() !== "") return { ok: true }

  const why = options.force
    ? "forçage refusé : la raison est vide"
    : "la tâche en cours du lot n'a pas de note (état non documenté)"
  return {
    ok: false,
    blocking,
    message:
      `${taskId} : ouverture refusée dans le lot ${lot} — ${blocking.id} est déjà en cours sans note (${why}). ` +
      `Fermer ou documenter ${blocking.id} (sdlc_track ${blocking.id} done|blocked "note"), ` +
      `ou forcer explicitement avec une raison (force: true, reason: "…").`,
  }
}

// ---------------------------------------------------------------------------
// Appel des scripts du dépôt
// ---------------------------------------------------------------------------

/** Chemin d'un script vendorisé : `<scriptsDir>/scripts/<nom>.py`. */
export function scriptPath(config: TrackerConfig, name: string): string {
  return join(config.scriptsDir, "scripts", name)
}

export function checkScriptPath(directory: string, config: TrackerConfig): string {
  return resolve(directory, config.checkScript)
}

/** Exécution réelle : binaire Python configurable, avec délai maximal. */
export function pythonRunner(config: TrackerConfig): RunScript {
  return (script, args, cwd) =>
    spawnCommand(config.pythonBin, [script, ...args], cwd, { timeoutMs: config.commandTimeoutMs })
}

/** Exécution réelle de git (statut, chemins touchés), bornée dans le temps. */
export function gitRunner(config: TrackerConfig): (args: string[], cwd: string) => Promise<ScriptResult> {
  return (args, cwd) => spawnCommand("git", args, cwd, { timeoutMs: config.commandTimeoutMs })
}

export type SpawnOptions = { timeoutMs?: number }

/**
 * Lance une commande et borne son exécution. À l'expiration : SIGKILL, code 124,
 * message explicite. Sans borne, un script bloqué gèlerait l'appel d'outil.
 */
export const spawnCommand = (
  command: string,
  args: string[],
  cwd: string,
  options: SpawnOptions = {},
): Promise<ScriptResult> =>
  new Promise<ScriptResult>((done) => {
    const timeoutMs = options.timeoutMs && options.timeoutMs > 0 ? options.timeoutMs : 10_000
    const child = spawn(command, args, { cwd })
    let stdout = ""
    let stderr = ""
    let settled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const finish = (result: ScriptResult) => {
      if (settled) return
      settled = true
      if (timer) clearTimeout(timer)
      done(result)
    }

    timer = setTimeout(() => {
      stderr += `${stderr ? "\n" : ""}[ai-sdlc-tracker] timeout après ${timeoutMs} ms`
      child.kill("SIGKILL")
      finish({ code: 124, stdout, stderr })
    }, timeoutMs)

    child.stdout.on("data", (chunk) => (stdout += String(chunk)))
    child.stderr.on("data", (chunk) => (stderr += String(chunk)))
    child.on("error", (error) => finish({ code: 127, stdout, stderr: `${stderr}${error.message}` }))
    child.on("close", (code) => finish({ code: code ?? 1, stdout, stderr }))
  })
