# Fiches opérationnelles — profil `on-prem`

<!-- À intégrer dans docs/ops/runbook.md (skill runbook). Remplacer les {{…}}. -->

## Fiche — Service indisponible après la mise à jour

**Priorité :** critique
**Seuils d'alerte :** le service ne répond pas après la fenêtre ; erreurs dans
les journaux.

**Diagnostic :**

1. Vérifier l'état des services : `{{commande-etat-services}}`.
2. Lire les journaux : `{{commande-journaux}}`.
3. Identifier si la cause vient du paquet ou d'une migration.

**Remédiation :**

- Appliquer le rollback (§ 4 du deploy) : réinstaller `{{version-precedente}}`
  et restaurer la base.

**Escalade :** coordonner immédiatement avec `{{contact-client-astreinte}}` et
ouvrir un incident (`docs/incidents/`).

## Fiche — Base de données injoignable

**Priorité :** critique
**Seuils d'alerte :** erreurs de connexion ; santé en échec.

**Diagnostic :**

1. Vérifier l'état du service de base : `{{commande-etat-base}}`.
2. Contrôler les ressources (disque, mémoire) et les journaux de la base.

**Remédiation :**

- Redémarrer le service de base si nécessaire.
- Restaurer depuis la sauvegarde si corruption avérée.

**Escalade :** perte de données possible → escalader à `{{responsable-ops}}` et
au client sans délai.

## Fiche — Espace disque insuffisant

**Priorité :** haute
**Seuils d'alerte :** `df -h` > 90 % ; écritures en échec.

**Diagnostic :**

1. `df -h` et `du -sh {{repertoire-donnees}}`.
2. Identifier journaux volumineux ou sauvegardes non purgées.

**Remédiation :**

- Purger les journaux/archives selon la politique convenue avec le client.
- Archiver les sauvegardes anciennes sur support externe.

**Escalade :** si le disque doit être agrandi, escalader à `{{responsable-infra}}`
et au client (matériel).

## Fiche — Certificat interne refusé ou expiré

**Priorité :** haute
**Seuils d'alerte :** erreurs TLS entre composants internes ; appels refusés.

**Diagnostic :**

1. Tester la chaîne : `{{commande-verification-certificat}}`.
2. Vérifier la date d'expiration et l'autorité de certification interne du client.

**Remédiation :**

- Installer le certificat renouvelé fourni par le client.

**Escalade :** renouvellement à demander à l'équipe sécurité du client
(`{{contact-pki}}`).
