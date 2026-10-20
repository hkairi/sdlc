# ADR-005 — Runner d'agents : préparation, lancement, budget, annulation

## Statut

Accepté — 2026-10-20.

Remplacé par : —

## Contexte

La Console doit permettre de **préparer et suivre** une revue indépendante, mais aussi de
**lancer un exécutant ou un relecteur depuis l'interface**. Cette capacité est puissante et
risquée : injection de commande, coût non borné, processus orphelins, écriture Git,
exfiltration de jetons, lancement sur un dépôt non déclaré.

Le framework interdit les commandes Git en écriture par les agents et exige un relecteur
différent de l'auteur, si possible avec un autre modèle.

## Décision

- **Modèles de commande configurés** par agent (`cli`, `models_json`, `role`, `enabled`,
  `max_concurrency`). Aucune commande libre n'est acceptée depuis l'interface.
- **Préflight obligatoire** avant confirmation : CLI présente, modèle disponible, dépôt
  déclaré, budget, durée max, rôle, commande exacte affichée.
- **Lancement dans un groupe de processus dédié** (session/process group) ; l'annulation
  envoie un signal au groupe, vérifie la terminaison, nettoie les fichiers temporaires.
- **Budget** : plafond en euros et en tokens, arrêt sur estimation cumulée ; à la fin, coût
  réel affiché et écart signalé. Le coût réel ne peut pas être garanti à l'euro près ; il est
  affiché, jamais masqué.
- **Timeout** et **limite de concurrence** par agent et par projet ; file d'attente locale.
- **Statuts fermés** : `queued`, `running`, `done`, `failed`, `timeout`, `cancelled` ;
  un run `queued` peut être annulé sans être exécuté.
- **Budget** : l'adaptateur expose la consommation à chaque appel ou périodiquement ; la
  Console échantillonne à cadence configurable (défaut 5 s), estime le cumul et arrête le
  groupe de processus au plafond. Le coût réel est affiché à la fin ; un dépassement est
  signalé, jamais masqué.
- **Environnement purgé** : les jetons GitHub/GitLab et secrets du serveur ne sont pas
  transmis au processus agent ; seules les variables explicitement nécessaires sont passées.
- **Lecture seule pour la revue** : l'adaptateur de l'agent applique `read-only`, l'absence de
  Git en écriture et, si disponible, l'absence de réseau. La Console ne peut pas garantir
  elle-même le sandbox : la limite est documentée et vérifiée par l'adaptateur.
- **Journal** : commande, agent, modèle, dépôt, tâche, début, fin, statut, coût, tokens,
  fichiers modifiés, rapport. Logs en texte échappé.
- Toute tentative d'écriture Git, de dépôt hors périmètre ou de commande non reconnue est
  **refusée et auditée**.

## Conséquences

### Positives

- L'humain pilote les agents depuis une vue unique, avec preuve et coût.
- Les runs sont reproductibles et auditables.
- Les risques sont contenus par des modèles, des budgets et des limites.
- Le relecteur peut être choisi pour son indépendance.

### Négatives

- Complexité du runner (process groups, signaux, budgets, logs) et tests multi-OS.
- Le sandbox reste délégué aux adaptateurs ; la Console ne peut pas tout garantir.
- Le coût réel peut dépasser légèrement l'estimation avant l'arrêt.
- Un agent peut échouer de façon opaque ; les logs doivent être conservés.

## Alternatives envisagées

| Alternative | Avantages | Inconvénients | Raison du rejet |
|---|---|---|---|
| Préparation/suivi seulement, exécution au CLI | Plus simple, moins risqué | L'utilisateur a demandé les deux | Ne répond pas au besoin |
| Runner avec commande libre | Flexible | Injection, secrets, dépôt arbitraire | Inacceptable |
| Orchestrateur externe (CI, queue) | Isolation, scalabilité | Infrastructure, hors local | Surdimensionné |
| Pas de limite de budget | Simple | Dérive de coût | Inacceptable |

## Références

- Cahier des charges §6.5, §6.11, §11, §17 : [`../00-cadrage/cahier-des-charges-web.md`](../../00-cadrage/cahier-des-charges-web.md)
- Revue contradictoire §3 et §4 : [`../00-cadrage/revue-cahier-des-charges-web.md`](../../00-cadrage/revue-cahier-des-charges-web.md)
- Analyse de menaces : [`../menaces.md`](../menaces.md)

---

*Date de proposition : 2026-10-20 — Date d'acceptation : 2026-10-20*
