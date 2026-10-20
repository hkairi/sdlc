/**
 * `sdlc_track` — statut + note d'une tâche ET case de `tasks.md`, en une opération.
 *
 * Ordre imposé : résolution de la cible (mono ou multi), puis les règles de
 * blocage (une seule tâche en cours par lot, preuve obligatoire pour `done`),
 * puis l'appel du script. Le retour nomme toujours le fichier modifié.
 */
import { canStartTask, noteHasEvidence, parseMonoTasks, parseMultiFeatures, resolveTarget, scriptPath } from "../core.ts"
import {
  evidenceFor,
  failure,
  inactive,
  optionalBoolean,
  optionalString,
  sdlcTool,
  scriptText,
  text,
} from "./shared.ts"
import type { Target } from "../core.ts"
import type { Deps } from "./shared.ts"
import type { ToolDef } from "../types.ts"

const STATUSES = ["todo", "doing", "blocked", "done"]

export function defineTrack(deps: Deps): ToolDef {
  return sdlcTool({
    name: "track",
    description:
      "Met à jour une tâche du suivi ET la case correspondante de tasks.md en une seule opération " +
      "(statut, date, note). Une tâche à la fois, tout de suite après le geste. " +
      "« done » exige une note avec un indice de vérification (chiffre, commande, « vérifié »). " +
      "Refuse d'ouvrir une deuxième tâche en cours dans le même lot (force + reason pour passer outre).",
    input: {
      type: "object",
      properties: {
        change: { type: "string", description: "identifiant exact du change OpenSpec" },
        task: { type: "string", description: "identifiant de tâche, par exemple 2.1" },
        status: { type: "string", enum: STATUSES },
        note: { type: "string", description: "fait / écart / vérifié (avec chiffres)" },
        force: { type: "boolean", description: "ouvrir malgré une tâche en cours dans le lot" },
        reason: { type: "string", description: "raison du forçage, obligatoire avec force" },
        file: { type: "string", description: "fichier de suivi à forcer (mono ou multi)" },
      },
      required: ["change", "task", "status"],
      additionalProperties: false,
    },
    async execute(input) {
      const off = inactive(deps)
      if (off) return text(off)

      const change = optionalString(input, "change") ?? failure("argument « change » requis")
      const task = optionalString(input, "task") ?? failure("argument « task » requis")
      const status = optionalString(input, "status") ?? failure("argument « status » requis")
      if (!STATUSES.includes(status)) {
        return text(`statut inconnu « ${status} » : attendu ${STATUSES.join(", ")}`)
      }
      const note = optionalString(input, "note")

      const resolved = resolveTarget(deps.directory, change, optionalString(input, "file"), deps.readFile)
      if (!resolved.ok) {
        return text(`track refusé : ${resolved.message}\nSuivis disponibles : ${resolved.candidates.join(", ")}`)
      }
      const { target } = resolved
      const known = target.tasks.find((item) => item.id === task)
      if (!known) {
        const ids = target.tasks.map((item) => item.id).join(", ") || "aucune"
        return text(`${target.file} : tâche ${task} introuvable. Identifiants : ${ids}`)
      }

      if (status === "doing" && deps.config.blockNextTask) {
        const decision = canStartTask(target.tasks, task, {
          force: optionalBoolean(input, "force") === true,
          reason: optionalString(input, "reason"),
        })
        if (!decision.ok) return text(`track refusé : ${decision.message}`)
      }

      if (status === "done") {
        if (!note) {
          return text(
            `${task} : note obligatoire pour passer à done — écrire ce qui a été fait et ce qui a été vérifié, ` +
              `par exemple « Fait : … ; vérifié : 30 tests, 0 échec ».`,
          )
        }
        const evidence = evidenceFor(deps)
        if (deps.config.requireEvidence && !noteHasEvidence(note, evidence)) {
          return text(
            `${task} : note sans indice de vérification — citer un résultat ou une commande ` +
              `(par exemple « npm test : 30 tests, 0 échec »). Motif appliqué : celui de ${deps.config.checkScript} ` +
              `(source : ${evidence.source}).`,
          )
        }
      }

      const script =
        target.kind === "mono"
          ? scriptPath(deps.config, "track.py")
          : scriptPath(deps.config, "track_multi.py")
      const args = ["--file", target.file]
      if (target.kind === "mono" && target.tasksFile) args.push("--tasks", target.tasksFile)
      args.push(target.kind === "multi" ? `${target.feature}:${task}` : task, status)
      if (note) args.push(note)

      const result = await deps.runScript(script, args, deps.directory)
      const forced = optionalBoolean(input, "force") === true && status === "doing"
      const suffix = forced ? ` (forçage : ${optionalString(input, "reason") ?? ""})` : ""

      // Contrôle optimiste : après l'écriture, l'état demandé doit être présent.
      // Sinon, un tiers a écrit entre-temps (ou le script n'a rien appliqué) : on le
      // dit au lieu de présenter un succès qui n'existe pas. Aucun verrou n'est posé —
      // les écrivains manuels (scripts de la skill) n'y participeraient pas.
      const warnings: string[] = []
      if (result.code === 0) {
        const actual = readTaskStatus(deps, target, task)
        if (actual !== status) {
          warnings.push(
            `⚠ ${task} n'est pas à « ${status} » dans ${target.file} après la mise à jour ` +
              `(lu : ${actual ?? "absent"}) — un autre écrivain a pu modifier le fichier entre-temps, ` +
              `ou le script n'a rien appliqué. Relancer sdlc_track.`,
          )
        }
        if (target.tasksFile) {
          const checked = readTasksCheckbox(deps, target.tasksFile, task)
          if (checked !== undefined && checked !== (status === "done")) {
            warnings.push(
              `⚠ la case ${task} de ${target.tasksFile} n'est pas ${status === "done" ? "cochée" : "décochée"} ` +
                `après la mise à jour — vérifier la cohérence avant de continuer.`,
            )
          }
        }
      }

      return text(
        [`${target.file} · ${target.feature ? `${target.feature}:` : ""}${task} → ${status}${suffix}`,
          scriptText("track", result),
          ...warnings].join("\n"),
      )
    },
  })
}

/** Statut réellement présent dans le suivi, après l'appel. */
export function readTaskStatus(deps: Deps, target: Target, taskId: string): string | undefined {
  try {
    const content = deps.readFile(target.file)
    if (target.kind === "multi") {
      const feature = parseMultiFeatures(content).find((item) => item.key === target.feature)
      return feature?.tasks.find((task) => task.id === taskId)?.status
    }
    return parseMonoTasks(content).find((task) => task.id === taskId)?.status
  } catch {
    return undefined
  }
}

/** Case de `tasks.md` pour une tâche : true = cochée, undefined = introuvable. */
export function readTasksCheckbox(deps: Deps, tasksFile: string, taskId: string): boolean | undefined {
  try {
    const line = deps
      .readFile(tasksFile)
      .split("\n")
      .find((candidate) => new RegExp(`^\\s*-\\s+\\[[ xX]\\]\\s+${taskId.replace(/\./g, "\\.")}\\s`).test(candidate))
    if (!line) return undefined
    return /^\s*-\s+\[[xX]\]/.test(line)
  } catch {
    return undefined
  }
}
