#!/usr/bin/env python3
"""tracking.py — logique commune des scripts `track*.py`.

Résolution d'un chantier / d'une tâche, application des rôles et de l'escalade, synchronisation
de la case du `tasks.md`, écriture atomique de `state.json` puis régénération du HTML.
"""
import os
import re
import sys

import state_io as sio


def resolve_feature(state, fid=None):
    feats = state.get("features") or []
    if fid:
        feat = sio.find_feature(state, fid)
        if not feat:
            sys.exit("Chantier '%s' introuvable." % fid)
        return feat
    if len(feats) == 1:
        return feats[0]
    ids = ", ".join(f.get("id", "?") for f in feats)
    sys.exit("Plusieurs chantiers : préciser --feature (ou 'chantier:tâche'). Candidats : %s" % ids)


def resolve_task(state, ident, fid=None):
    """Retourne (feature, task) depuis 'chantier:tâche', 'tâche' + --feature, ou 'tâche' unique."""
    if ":" in ident:
        fid2, tid = ident.split(":", 1)
        feat = sio.find_feature(state, fid2)
        if not feat:
            sys.exit("Chantier '%s' introuvable." % fid2)
        task = sio.find_task(feat, tid)
        if not task:
            sys.exit("Tâche '%s' introuvable dans le chantier '%s'." % (tid, fid2))
        return feat, task
    if fid:
        feat = sio.find_feature(state, fid)
        if not feat:
            sys.exit("Chantier '%s' introuvable." % fid)
        task = sio.find_task(feat, ident)
        if not task:
            sys.exit("Tâche '%s' introuvable dans le chantier '%s'." % (ident, fid))
        return feat, task
    hits = [(f, t) for f in state.get("features") or []
            for t in (f.get("tasks") or []) if t.get("id") == ident]
    if not hits:
        sys.exit("Tâche '%s' introuvable." % ident)
    if len(hits) > 1:
        ids = ", ".join("%s:%s" % (f["id"], t["id"]) for f, t in hits)
        sys.exit("Identifiant '%s' ambigu — préciser le chantier : %s" % (ident, ids))
    return hits[0]


def apply_roles(task, executor=None, reviewer=None, iteration=None,
                commit_message=None, ready_to_commit=False):
    """Pose les rôles sur la tâche. Refuse un relecteur égal à l'exécutant."""
    if executor is not None:
        task["executor"] = executor or None
    if reviewer is not None:
        task["reviewer"] = reviewer or None
    final_executor = task.get("executor")
    final_reviewer = task.get("reviewer")
    if final_executor and final_reviewer and final_executor == final_reviewer:
        sys.exit("Refusé : le relecteur ne peut pas être l'exécutant de la tâche ('%s')." % final_executor)
    if iteration is not None:
        try:
            task["review_iteration"] = int(iteration)
        except (TypeError, ValueError):
            sys.exit("--iteration attend un entier (reçu %r)." % iteration)
    if commit_message is not None:
        task["commit_message"] = commit_message or None
    if ready_to_commit:
        task["ready_to_commit"] = True


def apply_escalation(task, config_path=sio.DEFAULT_CONFIG_PATH, note=None):
    """Passe la tâche en blocked + escalated si l'itération dépasse le maximum configuré."""
    iteration = task.get("review_iteration")
    if not isinstance(iteration, int):
        return False
    maximum = sio.read_max_review_iterations(config_path)
    if iteration <= maximum:
        return False
    task["status"] = "blocked"
    task["escalated"] = True
    message = "Escalade : itération %d > max_review_iterations=%d (relecteur/relecture à réassigner)." % (iteration, maximum)
    existing = task.get("note") or ""
    if message not in existing:
        task["note"] = (existing + " " + message).strip() if existing else message
    sio.add_history(task, "blocked", task["note"])
    return True


def sync_tasks_md(feature, task_id, status, tasks_path=None):
    """Coche (done) ou décoche la case de la tâche dans le tasks.md du chantier."""
    path = tasks_path or feature.get("tasks_file")
    if not path:
        return
    if not os.path.isfile(path):
        if tasks_path:
            print("(avertissement) %s introuvable" % path, file=sys.stderr)
        return
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    mark = "x" if status == "done" else " "
    new, count = re.subn(r"^(\s*-\s+)\[[ xX]\](\s+%s\s)" % re.escape(task_id),
                         r"\1[%s]\2" % mark, text, count=1, flags=re.M)
    if count:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)
    else:
        print("(avertissement) %s absent de %s" % (task_id, path), file=sys.stderr)


def regenerate(state, state_path, out, root="."):
    """Régénère le HTML après écriture de l'état (`render.py`)."""
    import render
    return render.render(state=state, out=out, state_path=state_path, root=root)


def _finish(feature, state, state_path, out, root):
    """Recalcule les statuts, écrit l'état (atomique) puis régénère le HTML."""
    import phases as ph
    feature["blocked"] = sum(1 for t in feature.get("tasks") or [] if t.get("status") == "blocked")
    ph.refresh_statuses(feature.get("phases"), feature.get("tasks"))
    state["file_updated"] = sio.today()
    sio.save_state(state_path, state)
    regenerate(state, state_path, out, root)


def task_update_main(description):
    """CLI partagée par `track.py` et `track_multi.py` (arguments compatibles)."""
    import argparse
    ap = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True, help="fichier HTML de suivi à régénérer")
    ap.add_argument("--state", default=sio.DEFAULT_STATE_PATH, help="chemin de state.json")
    ap.add_argument("--tasks", help="tasks.md à cocher (sinon : tasks_file du chantier)")
    ap.add_argument("--feature", help="identifiant du chantier (si plusieurs)")
    ap.add_argument("--executor", help="exécutant de la tâche")
    ap.add_argument("--reviewer", help="relecteur (différent de l'exécutant)")
    ap.add_argument("--iteration", help="numéro d'itération de revue (entier)")
    ap.add_argument("--commit-message", dest="commit_message", help="message de commit proposé")
    ap.add_argument("--ready-to-commit", dest="ready_to_commit", action="store_true",
                    help="marquer la tâche prête à commiter")
    ap.add_argument("ident", help="<tâche> ou <chantier>:<tâche>")
    ap.add_argument("status", choices=list(sio.STATUSES))
    ap.add_argument("note", nargs="?")
    ap.add_argument("--config", default=sio.DEFAULT_CONFIG_PATH, help="sdlc.config.yaml")
    ap.add_argument("--root", default=".", help="racine du projet (résolution des sources)")
    args = ap.parse_args()

    state = sio.load_state(args.state)
    feature, task = resolve_task(state, args.ident, args.feature)
    key = "%s:%s" % (feature.get("id"), task.get("id"))

    # `--tasks` : recharge le texte complet et le titre court de la tâche depuis le tasks.md
    # (le statut, la note, l'historique et les rôles restent inchangés).
    if args.tasks and os.path.isfile(args.tasks):
        import generate as gen
        gen.reload_task_texts(feature, args.tasks)

    task["status"] = args.status
    task["updated"] = sio.today()
    if args.note is not None:
        task["note"] = args.note
    apply_roles(task, args.executor, args.reviewer, args.iteration,
                args.commit_message, args.ready_to_commit)
    escalated = apply_escalation(task, args.config)
    note = task.get("note") or {"todo": "À faire.", "doing": "En cours.",
                                "blocked": "Bloqué.", "done": "Terminé."}[task["status"]]
    sio.add_history(task, task["status"], note)

    _finish(feature, state, args.state, args.file, args.root)
    sync_tasks_md(feature, task["id"], task["status"], args.tasks)
    suffix = " (escalade)" if escalated else ""
    print("%s -> %s%s" % (key, task["status"], suffix))
    return 0


def phase_update_main(description):
    """CLI de `track_phase.py` (arguments compatibles)."""
    import argparse
    ap = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True, help="fichier HTML de suivi à régénérer")
    ap.add_argument("--state", default=sio.DEFAULT_STATE_PATH, help="chemin de state.json")
    ap.add_argument("--feature", help="identifiant du chantier")
    ap.add_argument("--root", default=".", help="racine du projet")
    ap.add_argument("ident", help="<phase>.<item> ou <chantier>:<phase>.<item>")
    ap.add_argument("status", choices=list(sio.STATUSES))
    ap.add_argument("note", nargs="?")
    args = ap.parse_args()

    ident = args.ident
    feature_id = args.feature
    if ":" in ident and "." in ident.split(":", 1)[1]:
        feature_id, ident = ident.split(":", 1)
    if "." not in ident:
        sys.exit("Identifiant attendu : <phase>.<item> (reçu « %s »)." % ident)
    pid, iid = ident.split(".", 1)
    if pid == "impl":
        sys.exit("La phase 'impl' est dérivée des tâches : la mettre à jour via track.py / track_multi.py.")

    state = sio.load_state(args.state)
    feature = resolve_feature(state, feature_id)
    phase = next((p for p in (feature.get("phases") or []) if p.get("id") == pid), None)
    if not phase:
        sys.exit("Phase '%s' introuvable." % pid)
    item = next((i for i in (phase.get("items") or []) if i.get("id") == iid), None)
    if not item:
        sys.exit("Item '%s' introuvable dans la phase '%s'." % (iid, pid))

    item["status"] = args.status
    item["updated"] = sio.today()
    if args.note is not None:
        item["note"] = args.note

    _finish(feature, state, args.state, args.file, args.root)
    scope = "%s:%s.%s" % (feature.get("id"), pid, iid) if len(state.get("features") or []) > 1 else "%s.%s" % (pid, iid)
    print("%s -> %s" % (scope, args.status))
    return 0
