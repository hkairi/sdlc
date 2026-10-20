# Déploiement — {{composant}} (profil `on-prem`)

<!-- Procédure destinée à docs/ops/deploy-{{composant}}.md (skill deploy-procedure).
     Remplacer les marqueurs {{…}} puis supprimer les consignes. -->

## 1. Prérequis

- [ ] `scripts/ci.sh` est **vert**.
- [ ] Le gate **go/no-go** est validé (`gates.go_no_go`).
- [ ] La **fenêtre de maintenance** est convenue avec le client
      (`{{fenetre-maintenance}}`) et communiquée aux utilisateurs.
- [ ] Les **accès** et habilitations sont obtenus (`{{acces-client}}`).
- [ ] Le **paquet versionné** est prêt (`{{format-paquet}}`, `{{version}}`) et sa
      somme de contrôle est vérifiée.
- [ ] La version précédente est disponible sur site (`{{version-precedente}}`)
      pour le rollback.
- [ ] La **sauvegarde** (§ 5) a été faite et sa restauration est vérifiée.
- [ ] Le plan de rollback (§ 4) est validé par le client.

## 2. Étapes de déploiement

1. Arrêter proprement les services : `{{commande-arret-services}}`.
2. Faire la sauvegarde (§ 5) et noter son emplacement.
3. Copier le paquet sur site et vérifier sa somme de contrôle :
   `{{commande-verification-paquet}}`.
4. Installer le paquet : `{{commande-installation}}`.
5. Appliquer les migrations : `{{commande-migration}}`.
6. Redémarrer les services : `{{commande-demarrage-services}}`.

## 3. Vérifications

- [ ] Les services sont actifs : `{{commande-etat-services}}`.
- [ ] La route de santé répond : `curl -fsS {{url-sante}}`.
- [ ] Les journaux ne montrent pas d'erreur : `{{commande-journaux}}`.
- [ ] Parcours critique OK (test conjoint avec le client) : `{{parcours-critique}}`.
- [ ] La version installée est la bonne : `{{commande-verification-version}}`.

## 4. Rollback

1. Arrêter les services : `{{commande-arret-services}}`.
2. Réinstaller la version précédente : `{{commande-installation-precedente}}`.
3. Restaurer la base depuis la sauvegarde (§ 5) si une migration est en cause.
4. Redémarrer et rejouer le § 3.

> Journaliser le rollback avec `result: "rollback"`.

## 5. Sauvegarde

1. Dump chiffré de la base : `{{commande-dump-base}}`.
2. Sauvegarde de la configuration et des fichiers de données :
   `{{commande-sauvegarde-config}}`.
3. **Vérifier** la restauration sur un environnement de test avant de poursuivre.

## 6. Journalisation

Ajouter une ligne dans `docs/journal/deploys.jsonl`, format § 12 :

```json
{"ts":"{{horodatage-iso-8601}}","env":"production","component":"{{composant}}","version":"{{version}}","result":"success","duration_s":null,"by":"{{operateur-ou-pipeline}}","note":"{{note}}"}
```

`result` ∈ `success` | `rollback` | `failed`. Champs inconnus : `null`.

---

*Responsable : {{responsable}} — Dernière mise à jour : {{date}}*
