# Fiches opérationnelles — profil `serverless`

<!-- À intégrer dans docs/ops/runbook.md (skill runbook). Remplacer les {{…}}. -->

## Fiche — Dépassement de délai d'une fonction (timeout)

**Priorité :** haute
**Seuils d'alerte :** invocations en `Timeout` ; erreurs en hausse sur
`{{fonction}}`.

**Diagnostic :**

1. Consulter les journaux : `{{commande-journaux}}`.
2. Mesurer la durée et identifier l'appel lent (base, service externe).
3. Vérifier le délai configuré et la mémoire allouée.

**Remédiation :**

- Optimiser l'appel lent ou augmenter prudemment le délai/mémoire.
- Déplacer un traitement long vers une file asynchrone.

**Escalade :** si un service amont est la cause, escalader à
`{{responsable-ops}}`.

## Fiche — Limitation de débit (throttling)

**Priorité :** haute
**Seuils d'alerte :** invocations rejetées (`ThrottlingException`, `429`).

**Diagnostic :**

1. Relever le taux de rejets : `{{commande-metriques}}`.
2. Identifier la concurrence configurée et les limites du compte cloud.

**Remédiation :**

- Ajuster la concurrence réservée / les limites.
- Lisser les pics via une file.

**Escalade :** si une limite de compte doit être relevée, escalader à
`{{responsable-ops}}`.

## Fiche — Événements en échec accumulés dans la DLQ

**Priorité :** haute
**Seuils d'alerte :** le nombre de messages dans `{{nom-dlq}}` augmente.

**Diagnostic :**

1. Lister les messages de la DLQ : `{{commande-inspection-dlq}}`.
2. Identifier l'erreur commune (schéma, permission, dépendance).

**Remédiation :**

- Corriger la cause.
- Rejouer les messages une fois la correction déployée : `{{commande-rejeu-dlq}}`.

**Escalade :** perte de données possible → ouvrir un incident et escalader à
`{{responsable-ops}}`.

## Fiche — Erreur de permissions IAM

**Priorité :** moyenne
**Seuils d'alerte :** erreurs `AccessDenied` dans les journaux.

**Diagnostic :**

1. Relever l'action et la ressource refusées.
2. Comparer avec le rôle d'exécution `{{role-execution}}`.

**Remédiation :**

- Ajuster la politique minimale nécessaire, redéployer l'IaC.

**Escalade :** si l'accès relève de la sécurité, escalader à
`{{responsable-securite}}`.
