# Fiches opérationnelles — profil `package`

<!-- À intégrer dans docs/ops/runbook.md (skill runbook). Remplacer les {{…}}. -->

## Fiche — La publication n'apparaît pas sur le registre

**Priorité :** haute
**Seuils d'alerte :** la commande de publication réussit mais la version est
absente du registre ; échec d'installation en aval.

**Diagnostic :**

1. Vérifier la version publiée : `{{commande-verification-version}}`.
2. Contrôler les droits du jeton de publication et la file d'attente du registre
   (propagation parfois différée).

**Remédiation :**

- Rejouer la publication si elle n'a pas abouti.
- Vérifier que le numéro de version n'existe pas déjà (immuabilité).

**Escalade :** registre en incident (statut public) → escalader à
`{{responsable-ops}}`.

## Fiche — Dépendance cassée pour les consommateurs

**Priorité :** haute
**Seuils d'alerte :** signalements d'installation en échec après une publication.

**Diagnostic :**

1. Reproduire l'installation : `{{commande-installation-verification}}`.
2. Identifier la dépendance ou la contrainte SemVer en cause.

**Remédiation :**

- Publier une version corrective (patch).
- Déprécier la version fautive : `{{commande-deprecation}}`.

**Escalade :** rupture d'API large → coordonner une communication via
`{{responsable-produit}}`.

## Fiche — Checksum ou signature invalide

**Priorité :** haute
**Seuils d'alerte :** vérification d'intégrité du paquet en échec côté
consommateur.

**Diagnostic :**

1. Comparer l'empreinte publiée et l'empreinte locale.
2. Vérifier l'étape de signature/provenance du pipeline.

**Remédiation :**

- Corriger la chaîne de signature, republier avec un numéro de version incrémenté.

**Escalade :** suspicion d'altération → escalader immédiatement à
`{{responsable-securite}}`.

## Fiche — Numéro de version déjà publié

**Priorité :** moyenne
**Seuils d'alerte :** la publication rejette une version existante.

**Diagnostic :**

1. Confirmer que la version existe : `{{commande-verification-version}}`.
2. Vérifier le calcul de version du pipeline.

**Remédiation :**

- Incrémenter la version, ne jamais écraser une version publiée.

**Escalade :** si le calcul de version est structurellement faux, escalader à
`{{responsable-ops}}`.
