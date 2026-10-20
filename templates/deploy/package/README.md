# Profil `package` — bibliothèque publiée sur un registre

## Quand le choisir

Quand le livrable est une **bibliothèque ou un paquet** consommé par d'autres
projets : npm, PyPI, RubyGems, Maven Central, crates.io, Docker Hub, etc. Le
« déploiement » est la **publication d'une version** sur le registre.

## Préproduction

Publier d'abord une **version candidate** (`rc`) sur un **registre de test** ou
un canal de pré-version (`{{canal-preversion}}`) :

- npm : `next` / tag de distribution de test ;
- PyPI : TestPyPI ;
- RubyGems : `--pre` ;
- Maven : dépôt de staging.

Installer la version candidate depuis le registre de test dans un projet
consommateur et vérifier l'intégration avant la publication définitive.

## Stratégie de rollback

- Les versions publiées sont généralement **immuables** : la suppression
  (`unpublish`) est restreinte ou interdite.
- Le rollback consiste à **déprécier** (`deprecate`) la version fautive et à
  publier une **version corrective** (patch) immédiatement après.
- Documenter clairement la version dépréciée dans le `CHANGELOG`.

## Sauvegarde

- Les sources et le `CHANGELOG` sont dans le dépôt (sauvegarde principale).
- Les artefacts publiés restent sur le registre : ne pas compter sur leur
  suppression. Conserver une copie locale de l'artefact par version.
- Versionner la documentation et les exemples avec le code.

## Points d'attention

- Respecter le **versionnement sémantique** (SemVer) et les règles de rupture.
- Signer et publier les métadonnées de provenance si le registre le permet.
- Vérifier les dépendances transitives et la compatibilité ascendante.
