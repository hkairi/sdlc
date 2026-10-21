# Runbook d'exploitation — Console SDLC

> Ce document décrit les symptômes, diagnostics, remédiations et escalades de
> la Console locale. Toutes les commandes s'exécutent depuis la racine du projet.

## 1. Le serveur ne démarre pas

**Symptôme** : `sdlc-console serve` retourne un code non nul.

1. `sdlc-console doctor` — vérifier configuration, schéma, port et permissions.
2. `sdlc-console schema status` — une migration est peut-être requise.
3. Vérifier que le port `8765` est libre et que l'adresse est `127.0.0.2`.
4. Consulter le message : bind non loopback, configuration invalide et schéma
   plus récent sont refusés explicitement.

**Escalade** : humain responsable du poste, avec la sortie de `doctor`.

## 2. Chaîne d'audit invalide

**Symptôme** : `audit verify` retourne `valid: false`.

1. Ne pas purger ni modifier la base.
2. Sauvegarder immédiatement : `sdlc-console backup`.
3. Conserver `reports/` et la base pour analyse.
4. Escalade humaine : une altération d'audit bloque le démarrage et la purge.

## 3. Purge refusée

| Code | Cause | Action |
|---|---|---|
| `backup_too_old` | aucune sauvegarde vérifiée de moins de 24 h | `sdlc-console backup` puis vérifier |
| `purge_busy` | une ingestion est en cours | attendre la fin de l'ingestion |
| `confirmation_required` | `--confirm` absent | relire la commande et confirmer |
| `audit_invalid` | chaîne d'audit altérée | arrêter et escalader |

Une purge n'inclut jamais `audit_events`. Les suppressions et fichiers retirés
sont écrits dans un événement `purge.completed`.

## 4. Sauvegarde et restauration

```bash
sdlc-console backup --status
sdlc-console backup --verify backups/<id>.sqlite3
sdlc-console restore backups/<id>.sqlite3 --target data/restaure.sqlite3
```

La restauration vérifie l'intégrité SQLite et l'empreinte du manifeste. Toujours
restaurer dans un fichier neuf ; `--force` est réservé à une cible connue.

## 5. Gate en échec

1. Ouvrir la vue Gates ou `reports/gates/<gate>.json`.
2. Lire les contrôles, preuves et findings.
3. Corriger la cause ; une dérogation datée peut être créée pour un risque
   accepté, avec propriétaire, approbateur et expiration.
4. Relancer le gate ; un verdict vert sans artefact reste `not_run`.

## 6. Agent bloqué, timeout ou coût anormal

1. Vue Agents IA : vérifier statut, durée, coût, budget et journal SSE.
2. Annuler le run depuis l'API/IHM si nécessaire ; le groupe de processus est
   terminé.
3. Un timeout conserve les logs ; un dépassement de budget est signalé, jamais
   masqué.
4. Vérifier `max_review_iterations` et `task_timeout_min` dans la configuration.

## 7. Documentation périmée ou fichier généré

1. Vue Documentation : les documents « à revoir » sont signalés.
2. Ne jamais éditer un fichier portant « Fichier généré, ne pas modifier ».
3. Utiliser « Régénérer » pour le suivi et les rapports.

## 8. Supervision

- `/api/health` : version et état ;
- `reports/summary.json` : contrôles CI et seuils ;
- `docs/journal/deploys.jsonl` et `runs.jsonl` : journal local ;
- événements SSE : `/api/events` et `/api/projects/<id>/events`.

## Contacts

Escalade vers l'orchestrateur humain du projet. Aucun secret ne doit être
transmis dans un ticket, un log ou une capture d'écran.
