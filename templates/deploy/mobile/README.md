# Profil `mobile` — application mobile (stores)

## Quand le choisir

Quand le livrable est une **application mobile** distribuée par les magasins
d'applications (App Store, Google Play, stores internes). Le déploiement prend
la forme d'une **soumission de version** à la revue du magasin, avec une phase de
test avant publication.

## Préproduction

Utiliser les **canaux de test** natifs :

- **iOS** : TestFlight (test interne puis externe) ;
- **Android** : pistes Google Play (interne → fermée → ouverte) ;
- ou un canal bêta géré par l'outil de distribution (`{{canal-beta}}`).

Chaque build de test est identifié par un **numéro de build** unique et signé.

## Stratégie de rollback

- Les magasins ne permettent **pas** de revenir instantanément à une version
  précédente pour les utilisateurs ayant installé la nouvelle. Le rollback réel
  passe par :
  - une **publication corrective** (hotfix, voir la voie transverse `hotfix`) ;
  - ou la **désactivation côté serveur** d'une fonctionnalité via un **indicateur
    de fonctionnalité** (feature flag) `{{indicateur-fonctionnalite}}`.
- Prévoir systématiquement un mécanisme serveur permettant de neutraliser une
  fonctionnalité défectueuse sans mise à jour de l'application.

## Sauvegarde

- Les **sources** et les **artefacts signés** sont conservés (dépôt + registre de
  builds `{{registre-builds}}`).
- L'application mobile n'a pas de base locale critique : les données vivent côté
  serveur (sauvegardées par leur propre profil de déploiement).
- Conserver les **clés de signature** hors dépôt, avec leur procédure de
  restauration.

## Points d'attention

- Les délais de revue des magasins ne sont pas maîtrisés : prévoir la marge.
- La compatibilité ascendante des API est impérative (des versions anciennes
  restent installées).
- Surveiller les certificats et profils de provisionnement (expiration).
