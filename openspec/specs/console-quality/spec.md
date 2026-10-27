# console-quality Specification

## Purpose
TBD - created by archiving change console-sdlc. Update Purpose after archive.
## Requirements
### Requirement: Verdict de gate fondé sur des preuves

Le système SHALL calculer chaque verdict de gate à partir d'artefacts de preuve liés, et
SHALL refuser un verdict vert sans preuve. Les verdicts autorisés sont `pass`, `warn`,
`fail`, `waived`, `not_applicable` et `not_run`.

#### Scenario: Gate vert avec preuve
- **WHEN** un contrôle passe et son artefact de preuve est présent
- **THEN** le gate affiche `pass`
- **AND** un lien vers la preuve est disponible

#### Scenario: Gate sans preuve
- **WHEN** un contrôle attendu n'a produit aucun artefact
- **THEN** le gate affiche `not_run`
- **AND** il est traité comme `fail`

### Requirement: Gate de tests

Le système SHALL exécuter et lire les résultats de tests, refuser un échec, signaler un
test instable avec un ticket, et interdire un test ignoré sur le code modifié.

#### Scenario: Échec de test
- **WHEN** un test échoue
- **THEN** le gate tests est `fail`
- **AND** la suite, le test et la cause sont affichés

#### Scenario: Test instable
- **WHEN** un test est détecté instable
- **THEN** il est mis en quarantaine avec un ticket et une expiration
- **AND** la quarantaine est visible dans le rapport de gate

### Requirement: Gate de couverture à trois seuils

Le système SHALL vérifier la couverture globale, la couverture des lignes modifiées et la
couverture minimale par fichier, avec des seuils distincts.

#### Scenario: Couverture globale insuffisante
- **WHEN** la couverture globale est à 72 % pour un seuil de 80 %
- **THEN** le gate couverture est `fail`
- **AND** la preuve pointe vers le fichier Cobertura

#### Scenario: Lignes modifiées insuffisantes
- **WHEN** la couverture globale est suffisante mais les lignes modifiées sont à 84 % pour un seuil de 90 %
- **THEN** le gate couverture est `fail`
- **AND** le détail par fichier est affiché

### Requirement: Gate de sécurité

Le système SHALL analyser les dépendances, le code, les secrets, les conteneurs et l'IaC,
et SHALL bloquer une vulnérabilité critique ou haute atteignable.

#### Scenario: Vulnérabilité haute atteignable
- **WHEN** une CVE haute est atteignable par un chemin d'appel
- **THEN** le gate sécurité est `fail`
- **AND** le chemin d'atteignabilité et le correctif sont affichés

#### Scenario: Vulnérabilité non atteignable
- **WHEN** une CVE moyenne n'est pas atteignable
- **THEN** le gate affiche un avertissement
- **AND** une dérogation datée peut être demandée

### Requirement: Gate de performance

Le système SHALL distinguer la performance observée (budget p95/p99, bundle, requêtes,
mémoire) des signaux statiques (N+1, requête non bornée, I/O sync, regex, image). Une
régression observée au-delà du seuil configuré SHALL bloquer ; en dessous, elle SHALL
alerter. Un signal statique SHALL alerter.

#### Scenario: Régression observée
- **WHEN** le p95 de `/search` passe de 280 ms à 312 ms pour un budget de 300 ms
- **THEN** le gate performance est `fail` si la régression dépasse le seuil configuré
- **AND** il est `warn` en dessous de ce seuil
- **AND** la preuve `reports/perf/*.json` est liée

#### Scenario: Signal statique
- **WHEN** une requête non bornée est détectée
- **THEN** un avertissement est affiché avec le fichier et la ligne
- **AND** la revue est invitée à confirmer

### Requirement: Gate de données

Le système SHALL bloquer une migration destructive, une PII dans les logs ou une sauvegarde
non testée, et SHALL alerter sur une rétention non définie ou un chiffrement absent.

#### Scenario: Migration destructive
- **WHEN** une migration ajoute `NOT NULL` sans défaut sur une table de 2,1 M de lignes
- **THEN** le gate données est `fail`
- **AND** la migration et la ligne sont affichées
- **AND** aucune dérogation n'est acceptée sans sauvegarde et restauration testées

#### Scenario: PII dans les logs
- **WHEN** un email en clair est détecté dans un log
- **THEN** le gate données est `fail`
- **AND** le fichier et la ligne sont affichés

### Requirement: Gate i18n

Le système SHALL vérifier la parité des clés entre locales, les clés orphelines et les
chaînes codées en dur, lorsque le produit déclare plusieurs locales.

#### Scenario: Clés manquantes
- **WHEN** la locale `en` a 7 clés manquantes par rapport à `fr`
- **THEN** le gate i18n est `warn`
- **AND** les clés manquantes sont listées

### Requirement: Support des langages par tiers

Le système SHALL détecter tous les langages du projet et SHALL faire échouer le gate si un
langage n'a pas d'adaptateur. Les contrôles attendus dépendent du tier : tier 1 (tests,
couverture, SCA/SAST, performance, données), tier 2 (tests, SCA), tier 3 (non supporté).

#### Scenario: Langage sans adaptateur
- **WHEN** un dépôt contient des fichiers Kotlin sans adaptateur déclaré
- **THEN** le gate langages est `fail` avec `unsupported_language`
- **AND** aucun gate n'est affiché `not_run` silencieusement

#### Scenario: Tier 2 sans couverture
- **WHEN** un dépôt contient du SQL tier 2 sans couverture
- **THEN** le contrôle de couverture est `not_applicable` pour ce langage
- **AND** le gate couverture n'échoue pas à cause de ce langage

### Requirement: Dérogations datées

Le système SHALL permettre une dérogation motivée, avec propriétaire, approbateur et date
d'expiration. Une dérogation expirée SHALL repasser le gate en échec.

#### Scenario: Dérogation expirée
- **WHEN** une dérogation arrive à expiration
- **THEN** le gate repasse en `fail`
- **AND** l'expiration est visible dans la vue Gates

### Requirement: Source unique des seuils

Le système SHALL lire les seuils dans `sdlc.config.yaml` et SHALL stocker une empreinte de
configuration avec le cache des gates. Tout changement de configuration SHALL marquer les
gates « recalcul requis ».

#### Scenario: Changement de seuil
- **WHEN** le seuil de couverture passe de 80 % à 85 %
- **THEN** les gates utilisant l'ancienne empreinte sont marqués « recalcul requis »
- **AND** le prochain run utilise le nouveau seuil

