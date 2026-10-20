# Fiches opérationnelles — profil `kubernetes`

<!-- À intégrer dans docs/ops/runbook.md (skill runbook). Remplacer les {{…}}. -->

## Fiche — Pod en `CrashLoopBackOff`

**Priorité :** haute
**Seuils d'alerte :** pod en `CrashLoopBackOff` ou compteur de redémarrages
croissant ; santé en échec.

**Diagnostic :**

1. `kubectl get pods -n {{namespace}}` pour repérer le pod.
2. `kubectl logs -n {{namespace}} {{pod}} --previous` pour la cause du crash.
3. `kubectl describe pod -n {{namespace}} {{pod}}` (variables manquantes,
   `ConfigMap`/`Secret` absent).

**Remédiation :**

- Corriger la cause (variable, secret, image) puis redéployer.
- Rollback : `kubectl rollout undo deployment/{{composant}} -n {{namespace}}`.

**Escalade :** si le pod ne démarre pas après rollback, escalader à
`{{responsable-ops}}`.

## Fiche — `OOMKilled`

**Priorité :** haute
**Seuils d'alerte :** conteneur tué avec `Reason: OOMKilled`.

**Diagnostic :**

1. `kubectl describe pod -n {{namespace}} {{pod}}` (dernier état, limite mémoire).
2. Comparer l'usage réel et la `limit` mémoire du manifest.

**Remédiation :**

- Ajuster `resources.limits.memory` et `requests` selon la mesure.
- Corriger une fuite mémoire si la consommation croît sans borne.

**Escalade :** si l'usage dépasse durablement la capacité du nœud, escalader pour
un redimensionnement.

## Fiche — `ImagePullBackOff`

**Priorité :** moyenne
**Seuils d'alerte :** pod bloqué en `ImagePullBackOff` / `ErrImagePull`.

**Diagnostic :**

1. `kubectl describe pod -n {{namespace}} {{pod}}` (message exact).
2. Vérifier le nom et le tag de l'image, et l'existence du `imagePullSecret`.

**Remédiation :**

- Corriger le tag ou (re)créer le `imagePullSecret` `{{pull-secret}}`.
- Re-pousser l'image si elle a été supprimée du registre.

**Escalade :** registre indisponible → escalader à `{{responsable-infra}}`.

## Fiche — Rollout bloqué (`ProgressDeadlineExceeded`)

**Priorité :** haute
**Seuils d'alerte :** `kubectl rollout status` ne se termine pas ; deployment en
`ProgressDeadlineExceeded`.

**Diagnostic :**

1. `kubectl rollout status deployment/{{composant}} -n {{namespace}}`.
2. `kubectl get replicasets -n {{namespace}}` et `describe` du nouveau RS.
3. Vérifier `readinessProbe` (chemin, port, délais).

**Remédiation :**

- Corriger la sonde ou l'image, puis relancer le rollout.
- Rollback immédiat si le service est impacté :
  `kubectl rollout undo deployment/{{composant}} -n {{namespace}}`.

**Escalade :** impact de disponibilité → ouvrir un incident et escalader à
`{{responsable-ops}}`.
