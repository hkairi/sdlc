/**
 * `sdlc_status` — lecture d'état, en texte, sans effet de bord.
 *
 * Répond à « où en est-on ? » : progression par chantier, tâches en cours depuis
 * longtemps, tâches closes sans preuve, dérives du contrôle de synchronisation.
 *
 * Depuis le durcissement, la **dette connue** (baseline datée) est distinguée du
 * **neuf** : un outil qui crie six dérives historiques à chaque lecture est un
 * outil qu'on ignore, et un gate ignoré ne protège plus rien.
 */
import { join } from "node:path"
import { listSuivis, noteHasEvidence, parseMonoTasks, parseMultiFeatures, type TaskState } from "../core.ts"
import { evidenceFor, inactive, sdlcTool, text } from "./shared.ts"
import type { Deps } from "./shared.ts"
import type { ToolDef } from "../types.ts"

const MULTI = "docs/suivi-multi.html"
const STALE_DAYS = 7

function daysSince(date: string, today: Date): number | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return undefined
  const then = new Date(`${date}T00:00:00Z`)
  return Math.floor((today.getTime() - then.getTime()) / 86_400_000)
}

export type ChantierStatus = {
  label: string
  file: string
  tasks: TaskState[]
}

/** Suivis du dépôt, mono et multi, avec leurs tâches (sans doublon mono/multi). */
export function collectChantiers(deps: Deps): ChantierStatus[] {
  const out: ChantierStatus[] = []
  const seen = new Set<string>()

  for (const file of listSuivis(deps.directory)) {
    let html: string
    try {
      html = deps.readFile(file)
    } catch {
      continue
    }
    if (file.endsWith("suivi-multi.html")) continue
    const label = file.replace(/^docs\/suivi-|\.html$/g, "")
    seen.add(label)
    out.push({ label, file, tasks: parseMonoTasks(html) })
  }

  const multiFile = listSuivis(deps.directory).find((file) => file.endsWith("suivi-multi.html"))
  if (multiFile) {
    let html = ""
    try {
      html = deps.readFile(multiFile)
    } catch {
      html = ""
    }
    for (const feature of parseMultiFeatures(html)) {
      const label = feature.change ?? feature.key
      if (seen.has(label)) continue
      seen.add(label)
      out.push({ label, file: multiFile, tasks: feature.tasks })
    }
  }

  return out
}

export type Baseline = {
  generated: string
  drifts: Set<string>
  unproven: Map<string, Set<string>>
}

/** Baseline de dette, si elle existe. Son absence n'empêche rien : tout est « nouveau ». */
export function loadBaseline(deps: Deps): Baseline | undefined {
  try {
    const raw = deps.readFile(join(deps.config.scriptsDir, "baseline.json"))
    const data = JSON.parse(raw) as {
      generated?: string
      drifts?: string[]
      unproven?: Record<string, string[]>
    }
    return {
      generated: data.generated ?? "date inconnue",
      drifts: new Set((data.drifts ?? []).map((drift) => drift.trim())),
      unproven: new Map(Object.entries(data.unproven ?? {}).map(([change, tasks]) => [change, new Set(tasks)])),
    }
  } catch {
    return undefined
  }
}

export function defineStatus(deps: Deps): ToolDef {
  return sdlcTool({
    name: "status",
    description:
      "État d'avancement, en lecture seule : progression par chantier, tâches en cours depuis plus de sept " +
      "jours, tâches terminées sans preuve chiffrée, dérives suivi ↔ tasks.md. Distingue les problèmes " +
      "nouveaux de la dette connue (baseline datée). N'écrit aucun fichier.",
    input: {
      type: "object",
      properties: {
        change: { type: "string", description: "limiter l'état à un chantier" },
      },
      additionalProperties: false,
    },
    async execute(input) {
      const off = inactive(deps)
      if (off) return text(off)

      const only = (input as { change?: string } | undefined)?.change
      const evidence = evidenceFor(deps)
      const baseline = loadBaseline(deps)
      const today = new Date()
      const chantiers = collectChantiers(deps).filter((c) => !only || c.label === only || c.file === only)

      if (chantiers.length === 0) {
        return text(only ? `aucun chantier ne correspond à « ${only} »` : "aucun suivi trouvé dans docs/")
      }

      const lines: string[] = []
      const total = { done: 0, all: 0, stale: 0, freshUnproven: 0, knownUnproven: 0 }

      for (const chantier of chantiers) {
        const done = chantier.tasks.filter((t) => t.status === "done").length
        const doing = chantier.tasks.filter((t) => t.status === "doing")
        const stale = doing.filter((t) => (daysSince(t.updated, today) ?? 0) > STALE_DAYS)
        const unproven = chantier.tasks.filter(
          (t) => t.status === "done" && !noteHasEvidence(t.note, evidence),
        )
        const knownIds = baseline?.unproven.get(chantier.label)
        const fresh = unproven.filter((t) => !knownIds?.has(t.id))
        const known = unproven.length - fresh.length

        total.done += done
        total.all += chantier.tasks.length
        total.stale += stale.length
        total.freshUnproven += fresh.length
        total.knownUnproven += known

        const bits = [`${done}/${chantier.tasks.length}`]
        if (doing.length > 0) {
          const oldest = doing
            .map((t) => ({ id: t.id, days: daysSince(t.updated, today) ?? 0 }))
            .sort((a, b) => b.days - a.days)[0]
          bits.push(`${doing.length} en cours (${oldest.id} : ${oldest.days} j)`)
        }
        if (stale.length > 0) bits.push(`${stale.length} en cours depuis > ${STALE_DAYS} j`)
        if (fresh.length > 0) bits.push(`${fresh.length} done sans preuve`)
        else if (known > 0) bits.push(`${known} done sans preuve (connues)`)
        lines.push(`${chantier.label} — ${bits.join(" · ")}`)
        for (const task of stale.slice(0, 2)) {
          lines.push(
            `  · ${task.id} ${task.title || "(sans titre)"} — en cours depuis ${daysSince(task.updated, today)} j (${task.updated})`,
          )
        }
      }

      const check = await deps.runScript(deps.config.checkScript, ["--all", "--json"], deps.directory)
      let drift = ""
      try {
        const payload = JSON.parse(check.stdout) as { problems?: string[] }
        const problems = (payload.problems ?? []).map((problem) => problem.trim())
        const knownDrifts = baseline ? problems.filter((problem) => baseline.drifts.has(problem)).length : 0
        const freshDrifts = problems.length - knownDrifts
        drift = baseline
          ? `${freshDrifts} nouvelle(s) dérive(s) · ${knownDrifts} connue(s) depuis ${baseline.generated}`
          : `${problems.length} dérive(s)`
      } catch {
        drift = check.code === 0 ? "aucune dérive" : "contrôle indisponible"
      }

      const header = `État — ${chantiers.length} chantier(s) · ${total.done}/${total.all} tâches faites · ${drift}`
      const body = [...lines]
      if (total.freshUnproven > 0) {
        body.push(
          `À noter : ${total.freshUnproven} tâche(s) done sans indice de vérification` +
            (total.knownUnproven > 0 ? ` (+ ${total.knownUnproven} connue(s) dans la baseline).` : "."),
        )
      } else if (total.knownUnproven > 0) {
        body.push(`Dette gelée : ${total.knownUnproven} tâche(s) done sans preuve, connues depuis ${baseline?.generated}.`)
      }
      const capped = body.slice(0, 28)
      if (body.length > capped.length) {
        capped.push(`… et ${body.length - capped.length} ligne(s) — filtrer avec change: "<id>"`)
      }
      return text([header, ...capped].join("\n"))
    },
  })
}
