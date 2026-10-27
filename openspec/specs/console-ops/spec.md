# console-ops Specification

## Purpose
TBD - created by archiving change console-sdlc. Update Purpose after archive.
## Requirements
### Requirement: Déploiements et go/no-go

Le système SHALL afficher les environnements dev, préprod et prod, l'historique des
déploiements, les métriques DORA et une checklist go/no-go dont chaque case renvoie à une
preuve.

#### Scenario: Go/no-go bloqué
- **WHEN** un gate est en échec ou la recette est incomplète
- **THEN** le verdict go/no-go est « no-go »
- **AND** les conditions bloquantes sont listées

#### Scenario: Historique des déploiements
- **WHEN** `deploys.jsonl` contient un déploiement en rollback
- **THEN** l'historique affiche le rollback, la version et la date
- **AND** le change failure rate est recalculé

### Requirement: Documentation et fraîcheur

Le système SHALL lister les documents attendus (brief, exigences, ADR, specs, recette,
runbook, incidents, release notes), afficher leur fraîcheur et rendre le Markdown avec le
HTML brut désactivé. Tout document généré (fichier de suivi, rapports de gate, exports)
SHALL porter une mention visible « fichier généré, ne pas modifier » et SHALL être
régénéré, jamais édité à la main.

#### Scenario: Document généré
- **WHEN** un document est généré par la Console
- **THEN** il porte la mention « fichier généré, ne pas modifier »
- **AND** l'interface propose de le régénérer, pas de l'éditer

#### Scenario: Document périmé
- **WHEN** un document dépasse son échéance de revue
- **THEN** il est signalé « à revoir »
- **AND** la vue Documentation propose un lien vers le fichier

#### Scenario: XSS dans un document
- **WHEN** un document contient du HTML brut
- **THEN** il est affiché comme texte
- **AND** aucun script n'est exécuté

### Requirement: Configuration validée

Le système SHALL valider `sdlc.config.yaml` contre un schéma JSON, afficher la configuration
effective et indiquer l'origine de chaque donnée : déclarée, détectée ou mesurée.

#### Scenario: Configuration invalide
- **WHEN** une clé obligatoire manque ou a une valeur invalide
- **THEN** le démarrage est refusé avec un message explicite
- **AND** la clé fautive est indiquée

### Requirement: Audit chaîné par projet

Le système SHALL tenir une chaîne d'audit par projet, avec `hash = sha256(prev_hash +
payload)` et une génération. Il SHALL contrôler l'intégrité au démarrage, après une purge
d'audit et à la demande. Un échec SHALL bloquer le démarrage et alerter.

#### Scenario: Chaîne altérée
- **WHEN** un événement d'audit est modifié
- **THEN** le contrôle d'intégrité échoue
- **AND** le démarrage est bloqué avec une alerte

#### Scenario: Ancrage avant purge
- **WHEN** l'utilisateur purge l'audit explicitement
- **THEN** un événement d'ancrage clôt la génération
- **AND** une nouvelle chaîne démarre
- **AND** le contrôle d'intégrité de la nouvelle chaîne est valide

### Requirement: Rétention et purge

Le système SHALL appliquer une rétention de 12 mois par défaut, configurable par projet et
par table, exclure l'audit de la purge automatique, inclure les fichiers de logs et de
rapports, et exécuter la purge dans la même file que l'ingestion.

#### Scenario: Purge standard
- **WHEN** des commits ont plus de 12 mois et une sauvegarde récente est vérifiée
- **THEN** les commits sont supprimés
- **AND** l'audit est conservé
- **AND** l'opération est journalisée

#### Scenario: Purge pendant une ingestion
- **WHEN** une ingestion est en cours
- **THEN** la purge attend ou est refusée avec `purge_busy`
- **AND** aucune donnée n'est corrompue

#### Scenario: Sauvegarde trop ancienne
- **WHEN** la dernière sauvegarde vérifiée a plus de 24 h
- **THEN** la purge est refusée avec `backup_too_old`

### Requirement: Sauvegarde et restauration globales

Le système SHALL sauvegarder le fichier SQLite complet, vérifier la sauvegarde, permettre
une restauration testée et afficher l'âge de la dernière sauvegarde.

#### Scenario: Restauration
- **WHEN** l'utilisateur restaure une sauvegarde dans un fichier neuf
- **THEN** tous les projets et leurs données sont présents
- **AND** le contrôle d'intégrité de l'audit est valide

### Requirement: Migration de schéma

Le système SHALL vérifier la version du schéma au démarrage, proposer une migration après
sauvegarde si le schéma est antérieur, et refuser un schéma plus récent ou inconnu.

#### Scenario: Schéma plus récent
- **WHEN** la base a un schéma plus récent que l'application
- **THEN** le démarrage est refusé avec un message explicite
- **AND** aucune migration destructive n'est tentée

### Requirement: Diagnostic et observabilité

Le système SHALL fournir `doctor` (versions, chemins, permissions, schéma, port, jetons,
quotas), `/api/health`, des logs structurés et un contrôle d'intégrité. Il SHALL ne rien
envoyer à l'extérieur sans configuration explicite.

#### Scenario: Diagnostic complet
- **WHEN** `sdlc-console doctor` est exécuté
- **THEN** les versions, le port, le schéma et les permissions sont affichés
- **AND** un problème est signalé avec un code de retour non nul

### Requirement: Sécurité locale

Le système SHALL écouter uniquement sur `127.0.0.0/8`, refuser tout bind non loopback,
valider `Host`, `Origin` et `Referer`, désactiver CORS, exiger un jeton CSRF et un
`Content-Type: application/json` pour les écritures, et ne jamais stocker de secret en base
ni dans un log.

#### Scenario: Bind non loopback
- **WHEN** l'utilisateur lance le serveur sur `0.0.0.0` ou une IP LAN
- **THEN** le démarrage est refusé
- **AND** le message explique la règle de boucle locale

#### Scenario: Requête CSRF absente
- **WHEN** une écriture est envoyée sans `X-SDLC-CSRF`
- **THEN** la réponse est `403`
- **AND** aucune action n'est exécutée

#### Scenario: DNS rebinding
- **WHEN** une écriture arrive avec un `Host`, un `Origin` ou un `Referer` externe
- **THEN** la requête est refusée
- **AND** aucune action n'est exécutée

#### Scenario: Content-Type non JSON
- **WHEN** une écriture est envoyée sans `Content-Type: application/json`
- **THEN** la requête est refusée
- **AND** aucune action n'est exécutée
- **AND** CORS ne renvoie aucun en-tête d'autorisation cross-origin

### Requirement: Redaction étendue

Le système SHALL ne jamais écrire un secret ou un prompt dans un export JSON/CSV, un champ
agrégé (`stats_json`), un journal de run ou le paquet de revue. Le test du faux jeton SHALL
couvrir ces quatre destinations.

#### Scenario: Faux jeton dans un export
- **WHEN** un faux jeton est présent dans les données ingérées
- **THEN** il est masqué dans l'export JSON/CSV
- **AND** il est masqué dans `stats_json` et dans le journal
- **AND** le test de non-régression passe

### Requirement: En-têtes de sécurité et CSP

Le système SHALL envoyer une Content-Security-Policy restrictive, interdire le HTML brut
dans le rendu Markdown et les logs, et vérifier ces règles en revue.

#### Scenario: CSP active
- **WHEN** une page est servie
- **THEN** l'en-tête Content-Security-Policy est présent
- **AND** un contenu HTML brut n'est pas interprété

