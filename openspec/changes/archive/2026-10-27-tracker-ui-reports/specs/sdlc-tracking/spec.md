# sdlc-tracking — deltas (tracker-ui-reports)

## ADDED Requirements

### Requirement: Coquille de rendu des suivis

Les suivis (`docs/suivi-*.html`) et le rapport de clôture (`docs/rapport-*.html`) SHALL adopter
une coquille commune : barre latérale marine, barre supérieure, cartes/KPI, et **thème
clair/sombre** persistant. Le rendu MUST rester autonome (aucune ressource distante bloquante) et
le thème MUST être mémorisé (`localStorage`, clé `sdlc-theme`).

#### Scenario: Rendu mono avec coquille

- **WHEN** une seule feature est suivie et le suivi est régénéré
- **THEN** le HTML expose la barre latérale, la barre supérieure, les KPI et le bouton de thème

#### Scenario: Bascule de thème persistante

- **WHEN** l'utilisateur bascule le thème clair/sombre puis recharge la page
- **THEN** le thème choisi est restauré

#### Scenario: Rapport de clôture à la même charte

- **WHEN** `sdlc_report` génère `docs/rapport-<change>.html`
- **THEN** le rapport reprend la charte (cartes KPI, badges de statut, bascule de thème) et reste autonome (aucun script externe ni ressource distante)

### Requirement: Menu Rapport de clôture intégré au suivi

Le suivi SHALL proposer un accès au rapport de clôture **dans l'interface**, et non par navigation
vers un fichier tiers. Le lien MUST être **conditionnel** (affiché seulement si
`docs/rapport-<change>.html` existe) et MUST ouvrir le rapport dans un panneau intégré, avec une
option « ouvrir dans un onglet ». Le suivi MUST NOT embarquer le HTML du rapport (lien, pas
inclusion) et MUST NOT modifier le rapport.

#### Scenario: Rapport absent

- **WHEN** le suivi est régénéré sans `docs/rapport-<change>.html`
- **THEN** aucun lien ni panneau « Rapport de clôture » n'est présent

#### Scenario: Rapport présent

- **WHEN** `docs/rapport-<change>.html` existe et le suivi est régénéré
- **THEN** un lien « Rapport de clôture » et un panneau `<iframe>` pointant vers ce rapport sont présents, et le clic ouvre le rapport sans quitter le suivi

#### Scenario: Suivi multi

- **WHEN** plusieurs chantiers sont suivis et qu'un rapport existe pour l'un d'eux
- **THEN** un lien « Rapport » par chantier ouvre le rapport concerné (nouvel onglet), sans quitter le suivi

### Requirement: Sélection de phase unique et lisible

La carte « Phases du chantier » SHALL n'ouvrir qu'**une seule phase à la fois** ; la phase en cours
MUST être ouverte par défaut (en l'absence de choix mémorisé). La phase sélectionnée MUST rester
**visuellement distincte** quel que soit son statut (y compris terminée), et le clic sur une phase
MUST basculer son ouverture de façon déterministe.

#### Scenario: Phase en cours ouverte par défaut

- **WHEN** aucune phase n'a de choix mémorisé
- **THEN** la phase en cours (première non terminée, sinon la dernière) est ouverte

#### Scenario: Une seule phase ouverte

- **WHEN** l'utilisateur clique sur une phase fermée
- **THEN** cette phase s'ouvre et toutes les autres se ferment

#### Scenario: Sélection visible sur une phase terminée

- **WHEN** une phase terminée est sélectionnée
- **THEN** elle porte un anneau de sélection net, distinct des phases terminées non sélectionnées

## MODIFIED Requirements

### Requirement: La dette historique est gelée et datée

La dette de suivi connue SHALL être figée dans un `baseline.json` **daté**, versionné, produit par
`baseline.py` **dans la skill** (`scripts/baseline.py`). Le générateur MUST lire la source de vérité
`docs/suivi/state.json` (et non le HTML), MUST appeler le `check_sync.py` voisin pour les dérives,
et MUST écrire `baseline.json` **à la racine de la skill** — là où le plugin le lit. Aucune copie
legacy hors de la skill ne MUST subsister. `sdlc_status` distingue le neuf du connu ; le ratchet
(`--check-ratchet`) échoue si une dette résorbée reste listée, et la baseline est réputée périmée
au-delà de 30 jours.

#### Scenario: Génération de la baseline

- **WHEN** `baseline.py --write` est lancé depuis la racine du projet
- **THEN** il lit `docs/suivi/state.json`, appelle `check_sync.py --all --json`, et écrit `baseline.json` à la racine de la skill

#### Scenario: Baseline lue par le plugin

- **WHEN** le plugin `sdlc_status` charge la baseline
- **THEN** il lit `baseline.json` à la racine de la skill (même chemin que celui écrit par le générateur)

#### Scenario: Dette résorbée non retirée

- **WHEN** une dette listée dans la baseline a été payée mais figure encore dans le fichier
- **THEN** `baseline.py --check-ratchet` échoue et liste les entrées à retirer
