# Profil `on-prem` — installation chez le client

## Quand le choisir

Quand le logiciel est **installé sur l'infrastructure du client** (serveurs sur
site, réseau restreint, exigences de souveraineté ou de sécurité). L'équipe ne
contrôle ni le matériel, ni le réseau, ni les fenêtres de maintenance.

## Préproduction

Disposer d'un **environnement de recette** :

- une **réplique chez le client** (idéal) ou un environnement de recette interne
  reproduisant la cible (mêmes versions d'OS, base, réseau) ;
- exécuter les tests de bout en bout avant chaque fenêtre de maintenance ;
- définir la fenêtre de maintenance et la procédure de retour arrière avec le
  client.

## Stratégie de rollback

- Livrer sous forme de **paquet versionné** (`{{format-paquet}}`) et conserver la
  version précédente (`{{version-precedente}}`) sur site.
- Rollback = réinstaller le paquet précédent puis restaurer la base depuis la
  sauvegarde faite juste avant la mise à jour.
- Toujours prévoir un **point de restauration** validé avant de commencer.

## Sauvegarde

- Avant toute mise à jour : **dump chiffré de la base** et sauvegarde de la
  configuration, exportés et vérifiés.
- En environnement sans accès Internet : la sauvegarde reste **sur site**
  (support chiffré) selon la politique du client.
- Conserver la procédure de restauration, testée au moins une fois.

## Points d'attention

- Accès et habilitations à obtenir **à l'avance** auprès du client.
- Pas d'accès Internet : prévoir les dépendances et images hors ligne.
- Journaliser chaque intervention (traçabilité demandée par le client).
- Les contraintes de sécurité (pare-feu, certificats internes) sont fréquentes.
