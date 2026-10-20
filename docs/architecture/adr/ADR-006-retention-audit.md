# ADR-006 — Rétention 12 mois et intégrité de l'audit

## Statut

Accepté — 2026-10-20.

Remplacé par : —

## Contexte

La Console stocke des commits, MR, revues, runs, findings, déploiements et événements
d'audit. L'utilisateur a choisi une rétention de **12 mois par défaut, configurable**.

La revue contradictoire a signalé une contradiction : purger l'audit à 12 mois casse la
chaîne `hash = sha256(prev_hash + payload)` et rend l'audit « inviolable » invérifiable.
Une purge concurrente d'une ingestion peut aussi supprimer des lignes en cours de
réingestion.

## Décision

- **12 mois par défaut** pour commits, MR, revues, runs, findings, déploiements et documents,
  configurables par projet et par table.
- **L'audit est exclu de la purge automatique.** Il est conservé au-delà de 12 mois par
  défaut et ne peut être purgé que par une commande explicite (`purge --audit`) avec :
  - confirmation interactive et motif ;
  - sauvegarde récente vérifiée ;
  - écriture d'un **événement d'ancrage** qui clôt la chaîne et commence une nouvelle
    génération, documentée ;
  - contrôle d'intégrité après purge.
- **La purge passe par la même file que l'ingestion** ; elle attend la fin des ingestions et
  des runs de gate en cours, puis journalise le nombre de lignes supprimées par table. Les
  fichiers de logs et de rapports sont purgés avec la même règle.
- **Sauvegarde globale** : la base est un fichier unique ; `backup` sauvegarde tout le
  fichier, pas un projet. La vue projet n'affiche que l'âge de la dernière sauvegarde.
- **Chaîne d'audit par projet** : `prev_hash` et `generation` sont adossés au couple
  `(project_id, generation)` ; un contrôle d'intégrité est exécuté au démarrage, après purge
  d'audit et à la demande.
- **Sauvegarde avant purge** : `backup --verify` doit être récent ; sinon la purge est
  refusée.
- **Restauration** : la procédure est testée et documentée ; un échec de contrôle d'intégrité
  bloque le démarrage et alerte.

## Conséquences

### Positives

- Conformité et sobriété : les données opérationnelles ne s'accumulent pas indéfiniment.
- L'audit reste vérifiable et non tronqué silencieusement.
- La purge est prévisible, sauvegardée et traçable.
- Le comportement est testable (purge, concurrence, intégrité).

### Négatives

- L'audit occupe plus d'espace que les autres tables.
- La purge d'audit est une opération manuelle et plus lourde.
- La coordination avec l'ingestion ajoute de la complexité.
- Les volumes à 12 mois doivent être surveillés.

## Alternatives envisagées

| Alternative | Avantages | Inconvénients | Raison du rejet |
|---|---|---|---|
| Tout purger à 12 mois, audit inclus | Simple | Casse la chaîne de hachage | Inacceptable |
| Audit illimité | Intégrité maximale | Croissance non bornée | Acceptable en local, mais l'utilisateur veut 12 mois configurable |
| Purge avec ancrage annuel automatique | Compromis | Complexité, perte de continuité | Retenu comme option explicite, pas par défaut |
| Pas de purge | Simple | Croissance, conformité | Contraire à la décision |

## Références

- Cahier des charges §7, §8, §16 : [`../00-cadrage/cahier-des-charges-web.md`](../../00-cadrage/cahier-des-charges-web.md)
- Revue contradictoire §2 et §9 : [`../00-cadrage/revue-cahier-des-charges-web.md`](../../00-cadrage/revue-cahier-des-charges-web.md)

---

*Date de proposition : 2026-10-20 — Date d'acceptation : 2026-10-20*
