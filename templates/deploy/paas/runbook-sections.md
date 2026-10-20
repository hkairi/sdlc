# Fiches opérationnelles — profil `paas`

<!-- À intégrer dans docs/ops/runbook.md (skill runbook). Remplacer les {{…}}. -->

## Fiche — L'application ne démarre pas (« boot timeout »)

**Priorité :** haute
**Seuils d'alerte :** la release précédente est conservée ; l'appli renvoie une
erreur de démarrage ; la plateforme signale un dépassement du délai de boot.

**Diagnostic :**

1. Lire les journaux de la release en échec : `{{commande-journaux}}`.
2. Vérifier la commande de démarrage (`Procfile`, `start` script) et le port
   d'écoute (`PORT`).
3. Contrôler les variables d'environnement requises.

**Remédiation :**

- Corriger la cause, redéployer.
- Rollback sur la release précédente : `{{commande-rollback-release}}`.

**Escalade :** si la plateforme est en incident (statut public), escalader à
`{{responsable-ops}}`.

## Fiche — Erreurs 502 / 503 en production

**Priorité :** critique
**Seuils d'alerte :** taux d'erreurs 5xx élevé ; route de santé en échec.

**Diagnostic :**

1. `curl -fsS {{url-sante}}` et relever le code.
2. Journaux : `{{commande-journaux}}`.
3. Vérifier la saturation des ressources (dynos/instances) et la base.

**Remédiation :**

- Redémarrer/redimensionner si saturation.
- Rollback si l'erreur suit un déploiement récent.

**Escalade :** impact client → ouvrir un incident (`docs/incidents/`) et escalader
immédiatement.

## Fiche — Connexions à la base de données saturées

**Priorité :** haute
**Seuils d'alerte :** erreurs « too many connections » ; latence en hausse.

**Diagnostic :**

1. Relever le nombre de connexions côté base : `{{commande-connexions-base}}`.
2. Vérifier la configuration du pool de connexions de l'application.

**Remédiation :**

- Réduire la taille des pools ou libérer les connexions inactives.
- Monter en gamme l'addon base si le plafond est atteint durablement.

**Escalade :** saturation persistante → escalader pour un changement de plan.

## Fiche — Échec de build sur la plateforme

**Priorité :** moyenne
**Seuils d'alerte :** build de la release en échec ; déploiement non appliqué.

**Diagnostic :**

1. Lire la sortie de build : `{{commande-journaux-build}}`.
2. Reproduire le build en local avec la même version de langage.

**Remédiation :**

- Corriger le build, mettre à jour les verrous de dépendances, redéployer.

**Escalade :** si la plateforme impose une limite (taille, quota), escalader à
`{{responsable-ops}}`.
