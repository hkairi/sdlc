# Fiches opérationnelles — profil `vps-compose`

<!-- Fournit les fiches propres au profil, à intégrer dans docs/ops/runbook.md
     (skill runbook). Une fiche = symptôme → diagnostic → remédiation → escalade.
     Remplacer les marqueurs {{…}}. -->

## Fiche — Le conteneur {{composant}} redémarre en boucle

**Priorité :** haute
**Seuils d'alerte :** `docker compose ps` montre `Restarting` ou un compteur de
redémarrages croissant ; absence de réponse sur `{{url-sante}}`.

**Diagnostic :**

1. Lire les journaux : `docker compose logs --tail 200 {{composant}}`.
2. Distinguer une erreur applicative (trace) d'une erreur d'infrastructure
   (base injoignable, volume absent, permission).
3. Contrôler la variable d'environnement manquante ou invalide.

**Remédiation :**

- Corriger la cause (variable, migration, volume) puis `docker compose up -d`.
- En cas de doute, rollback sur `{{version-precedente}}` (voir `deploy.md` § 4).

**Escalade :** si le service ne redémarre pas après rollback, escalader à
`{{responsable-ops}}`.

## Fiche — Disque plein sur l'hôte

**Priorité :** haute
**Seuils d'alerte :** `df -h` > 90 % ; `docker system df` montre des images ou
volumes orphelins.

**Diagnostic :**

1. `df -h` et `du -sh {{repertoire-donnees}}` pour localiser.
2. `docker system df` pour les images, conteneurs et volumes.
3. Vérifier les journaux volumineux et les sauvegardes non purgées.

**Remédiation :**

- Purger sans risque : `docker image prune`, `docker builder prune`.
- Purger les journaux applicatifs selon la politique de rétention.
- Ne **jamais** supprimer un volume de données sans sauvegarde préalable.

**Escalade :** si l'espace reste insuffisant, escalader pour agrandir le volume
`{{volume}}`.

## Fiche — La base de données est injoignable

**Priorité :** critique
**Seuils d'alerte :** erreurs de connexion dans les journaux applicatifs ;
`curl {{url-sante}}` renvoie une erreur 5xx.

**Diagnostic :**

1. `docker compose ps` : le conteneur de base est-il `Up (healthy)` ?
2. `docker compose logs {{service-base}}`.
3. Vérifier les identifiants et la connectivité réseau entre services.

**Remédiation :**

- Redémarrer le service de base si nécessaire : `docker compose restart {{service-base}}`.
- Restaurer depuis la sauvegarde `vps-db-backup` en cas de corruption.

**Escalade :** corruption de données persistante → escalader immédiatement à
`{{responsable-ops}}` et ouvrir un incident (`docs/incidents/`).

## Fiche — Le certificat TLS a expiré

**Priorité :** haute
**Seuils d'alerte :** navigateurs en erreur ; `openssl s_client` montre une date
d'expiration dépassée.

**Diagnostic :**

1. Vérifier la date : `echo | openssl s_client -connect {{domaine}}:443 2>/dev/null | openssl x509 -noout -dates`.
2. Identifier l'outil de renouvellement (Certbot, reverse proxy).

**Remédiation :**

- Renouveler : `{{commande-renouvellement-certificat}}` puis recharger le proxy.
- Corriger la tâche planifiée si le renouvellement automatique a échoué.

**Escalade :** si le renouvellement échoue (validation DNS bloquée), escalader à
`{{responsable-infra}}`.
