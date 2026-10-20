# Profil `kubernetes` — cluster Kubernetes ou K3s

## Quand le choisir

Quand l'application est destinée à un **cluster Kubernetes** (managé ou K3s
auto-hébergé) : plusieurs composants, besoins de montée en charge, de
disponibilité et d'isolation par namespace. Profil adapté aux architectures
microservices.

## Préproduction

Utiliser un **namespace de préproduction** (`{{namespace-preprod}}`) sur le même
cluster (ou un cluster de recette dédié) :

- mêmes manifests que la production, avec des `values` différentes (Helm) ou des
  `overlays` (Kustomize) ;
- base de données et secrets de préproduction distincts ;
- ingress et nom de domaine de préproduction (`{{domaine-preprod}}`).

## Stratégie de rollback

- Déployer par **image immuable** (`{{registry}}/{{composant}}:{{version}}`).
- Conserver l'historique des `ReplicaSet` (par défaut) pour permettre
  `kubectl rollout undo`.
- Rollback applicatif : `kubectl rollout undo deployment/{{composant}} -n {{namespace}}`.
- Rollback Helm : `helm rollback {{release}} <revision>`.
- Les migrations de base suivent une procédure réversible ou une restauration.

## Sauvegarde

- **Volumes persistants** : sauvegarde via l'outil du cluster (ex. Velero) ou
  snapshot du fournisseur.
- **Base de données** : dump chiffré avant migration, conservé hors cluster.
- **Objets Kubernetes** : les manifests vivent dans le dépôt (Infrastructure as
  Code) ; ne pas compter sur le cluster comme source de vérité.

## Points d'attention

- Vérifier les `requests`/`limits` de ressources pour éviter `OOMKilled`.
- Les `Secrets` ne sont jamais en clair dans le dépôt.
- Contrôler les sondes (`readiness`, `liveness`) lors de chaque changement.
