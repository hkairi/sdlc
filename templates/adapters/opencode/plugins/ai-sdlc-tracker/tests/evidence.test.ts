import test from "node:test"
import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { resolve } from "node:path"
import { FALLBACK_EVIDENCE_PATTERNS, loadEvidencePattern, noteHasEvidence } from "../core.ts"

const REPO = resolve(import.meta.dirname, "fixtures/repo")
const CHECK_SYNC = resolve(REPO, "scripts/check_sync.py")

/** Verdict du script de contrôle lui-même, pour comparer — sans dupliquer la règle. */
function pythonVerdicts(notes: string[]): boolean[] {
  const code = [
    "import importlib.util, json, sys",
    "spec = importlib.util.spec_from_file_location('check_sync', sys.argv[1])",
    "mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)",
    "notes = json.load(sys.stdin)",
    "print(json.dumps([bool(mod.EVIDENCE_RE.search(n)) for n in notes]))",
  ].join("\n")
  const run = spawnSync("python3", ["-c", code, CHECK_SYNC], { input: JSON.stringify(notes), encoding: "utf-8" })
  assert.equal(run.status, 0, run.stderr)
  return JSON.parse(run.stdout) as boolean[]
}

const CORPUS = [
  "",
  "c'est fait",
  "terminé",
  "1654 examples, 0 failures",
  "go test ./... : ok",
  "rubocop : 0 offense",
  "exit=0",
  "vérifié",
  "18/18 scénarios conformes",
  "3 critères validés",
  "rien à signaler",
  "RSpec: 12 examples, 0 failures",
]

test("le motif de preuve est extrait du script de contrôle", () => {
  const evidence = loadEvidencePattern(CHECK_SYNC)
  assert.equal(evidence.source, "script")
  assert.ok(evidence.pattern.includes("make test"))
  assert.match(evidence.pattern, /examples\?/)
})

test("sans script disponible, le motif de repli est utilisé et signalé", () => {
  const evidence = loadEvidencePattern("/chemin/inexistant/check_sync.py")
  assert.equal(evidence.source, "fallback")
  assert.equal(evidence.pattern, FALLBACK_EVIDENCE_PATTERNS.join("|"))
})

test("la règle TS et la règle Python donnent le même verdict sur tout le corpus", () => {
  const evidence = loadEvidencePattern(CHECK_SYNC)
  const expected = pythonVerdicts(CORPUS)
  const actual = CORPUS.map((note) => noteHasEvidence(note, evidence))
  assert.deepEqual(actual, expected, `corpus : ${JSON.stringify(CORPUS)}`)
})

test("le corpus couvre bien des notes refusées et des notes acceptées", () => {
  const evidence = loadEvidencePattern(CHECK_SYNC)
  const verdicts = CORPUS.map((note) => noteHasEvidence(note, evidence))
  assert.ok(verdicts.includes(false), "au moins une note doit être refusée")
  assert.ok(verdicts.includes(true), "au moins une note doit être acceptée")
})

test("une divergence du motif du script fait échouer l'alignement", () => {
  // Simulation : un motif modifié qui n'exige plus rien de chiffré.
  const broken = { regex: /./, source: "script" as const, pattern: "." }
  const expected = pythonVerdicts(CORPUS)
  const actual = CORPUS.map((note) => noteHasEvidence(note, broken))
  assert.notDeepEqual(actual, expected, "le test d'alignement doit détecter une règle désaccordée")
})
