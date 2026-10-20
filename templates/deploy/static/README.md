# Profil `static` — site statique et CDN

## Quand le choisir

Quand le livrable est un **ensemble de fichiers statiques** (HTML, CSS, JS,
images) servi par un hébergeur/CDN : GitHub Pages, GitLab Pages, Netlify,
Cloudflare Pages, S3 + CloudFront… Aucun serveur applicatif.

## Préproduction

Utiliser les **environnements de prévisualisation** natifs de la plateforme :

- une **URL de prévisualisation par branche** ou par pull request
  (`{{strategie-preprod}}`) ;
- ou un bucket de préproduction distinct (`{{bucket-preprod}}`) ;
- publier d'abord l'artefact en préproduction, vérifier, puis promouvoir le
  **même artefact** en production.

## Stratégie de rollback

- Les fichiers sources vivent dans git : revenir au commit précédent
  (`{{version-precedente}}`) et republier.
- Repartir de l'**artefact du déploiement précédent** si la plateforme le
  conserve (releases / deploys).
- Après publication, **invalider le cache CDN** :
  `{{commande-invalidation-cdn}}`.

## Sauvegarde

- Les sources sont dans git : c'est la sauvegarde principale.
- Versionner les artefacts publiés (par tag) pour permettre le rollback.
- Les redirections/configuration de la plateforme (fichier `_redirects`,
  `headers`, règles CDN) doivent être dans le dépôt.

## Points d'attention

- Toujours invalider le cache après un changement de contenu ou de configuration.
- Vérifier les en-têtes de sécurité (CSP, HSTS) à chaque évolution.
- Contrôler les certificats TLS et les domaines personnalisés.
