# Fiches opérationnelles — profil `mobile`

<!-- À intégrer dans docs/ops/runbook.md (skill runbook). Remplacer les {{…}}. -->

## Fiche — Plantages au démarrage après une publication

**Priorité :** critique
**Seuils d'alerte :** pic de plantages au lancement (`{{tableau-de-bord-crashs}}`)
après une mise en production.

**Diagnostic :**

1. Identifier la version et le modèle d'appareil concernés.
2. Lire la trace de plantage (symbolisée) : `{{commande-lecture-crashs}}`.
3. Corréler avec les changements de la version.

**Remédiation :**

- Désactiver la fonctionnalité en cause via `{{indicateur-fonctionnalite}}`.
- Préparer un correctif et soumettre une version corrective (hotfix).

**Escalade :** impact large → ouvrir un incident (`docs/incidents/`) et escalader
immédiatement.

## Fiche — Version refusée par la revue du magasin

**Priorité :** moyenne
**Seuils d'alerte :** notification de rejet ; version non publiée.

**Diagnostic :**

1. Lire le motif de rejet fourni par le magasin.
2. Vérifier la conformité (permissions déclarées, politique de confidentialité,
   captures d'écran).

**Remédiation :**

- Corriger les points signalés, incrémenter le numéro de build, resoumettre.

**Escalade :** si le motif est ambigu, escalader à `{{responsable-produit}}`.

## Fiche — Certificat de signature ou profil expiré

**Priorité :** haute
**Seuils d'alerte :** échec de build/signature ; avertissement d'expiration du
profil de provisionnement.

**Diagnostic :**

1. Vérifier la date d'expiration du certificat et du profil.
2. Contrôler la correspondance certificat/profil/bundle id.

**Remédiation :**

- Renouveler le certificat/profil et reconstruire l'artefact signé.

**Escalade :** perte de la clé de signature → escalader à `{{responsable-mobile}}`
et appliquer la procédure de restauration des clés.

## Fiche — Version ancienne toujours installée (fragment de parc)

**Priorité :** moyenne
**Seuils d'alerte :** part importante du parc sur d'anciennes versions ; erreurs
d'API sur ces versions.

**Diagnostic :**

1. Consulter la répartition des versions (`{{tableau-de-bord-versions}}`).
2. Identifier les appels non rétrocompatibles.

**Remédiation :**

- Rétablir la rétrocompatibilité côté serveur (tolérance aux anciennes versions).
- Inviter à la mise à jour (message in-app), sans la rendre obligatoire.

**Escalade :** si le service serveur doit être rompu, coordonner avec
`{{responsable-produit}}`.
