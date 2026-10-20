# Fiches opérationnelles — profil `static`

<!-- À intégrer dans docs/ops/runbook.md (skill runbook). Remplacer les {{…}}. -->

## Fiche — Contenu obsolète servi après déploiement (cache CDN)

**Priorité :** moyenne
**Seuils d'alerte :** un utilisateur voit une ancienne version ; les fichiers
`{{fichier-hashé}}` ne correspondent pas à la release.

**Diagnostic :**

1. Vérifier la version réellement servie : `curl -sS {{url-production}} | head`.
2. Inspecter l'en-tête de cache (`cache-control`, `age`).
3. Comparer le hash/artefact déployé avec le contenu servi.

**Remédiation :**

- Invalider le cache : `{{commande-invalidation-cdn}}`.
- Si le contenu est réellement erroné, republier le bon artefact.

**Escalade :** si l'invalidation échoue côté fournisseur, escalader à
`{{responsable-ops}}`.

## Fiche — Pages en 404 après déploiement

**Priorité :** haute
**Seuils d'alerte :** pic de 404 sur des routes connues ; navigation cassée.

**Diagnostic :**

1. Lister les routes en 404 : `{{commande-journaux-acces}}`.
2. Vérifier les règles de réécriture/redirection et la racine de publication.

**Remédiation :**

- Corriger `{{fichier-config-hebergeur}}` (redirections, fallback SPA).
- Republier et invalider le cache.

**Escalade :** si le routage dépend du fournisseur, escalader à
`{{responsable-ops}}`.

## Fiche — Erreur de certificat TLS ou de domaine

**Priorité :** haute
**Seuils d'alerte :** avertissement de sécurité navigateur ; erreur de certificat.

**Diagnostic :**

1. `echo | openssl s_client -connect {{domaine}}:443 2>/dev/null | openssl x509 -noout -dates`.
2. Vérifier l'association du domaine personnalisé et la validation DNS.

**Remédiation :**

- Corriger les enregistrements DNS ou revalider le domaine sur la plateforme.
- Attendre le renouvellement automatique du certificat.

**Escalade :** validation DNS bloquée chez le registrar → escalader à
`{{responsable-infra}}`.

## Fiche — Ressource bloquée par la CSP

**Priorité :** moyenne
**Seuils d'alerte :** erreurs de console (violations CSP) ; styles/scripts non
chargés.

**Diagnostic :**

1. Relever les violations CSP dans la console navigateur ou via le rapport CSP.
2. Comparer la directive `content-security-policy` avec les sources réellement
   utilisées.

**Remédiation :**

- Ajuster la CSP (sources autorisées) dans `{{fichier-config-hebergeur}}`.
- Republier et invalider le cache.

**Escalade :** si la CSP est imposée par le client, coordonner avec
`{{responsable-securite}}`.
