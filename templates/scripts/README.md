# Contrôles automatiques (`scripts/ci.sh`)

Ce dossier contient la **définition unique des contrôles** du framework, appelée
en local comme en CI. Aucun pipeline ne réimplémente ces contrôles : il appelle
`scripts/ci.sh` et publie `reports/`.

## Fichiers

| Fichier | Rôle |
|---|---|
| `ci.sh` | Lance les contrôles, applique les seuils, écrit `reports/summary.json`. |
| `check_thresholds.py` | Calcule la couverture et compte les vulnérabilités SARIF ; appelé par `ci.sh`. |
| `tests/` | Tests unitaires de `check_thresholds.py` et jeux d'essai (`tests/fixtures/`). |

## Installation dans un projet

1. Copier `ci.sh` et `check_thresholds.py` à l'identique dans `scripts/` du projet.
2. Rendre `ci.sh` exécutable : `chmod +x scripts/ci.sh`.
3. Copier `tests/` si le projet souhaite exécuter les tests unitaires des seuils.
4. Déclarer `reports/` comme non versionné (`.gitignore`).

## Utilisation

```sh
scripts/ci.sh                       # tous les contrôles
scripts/ci.sh --only tests,coverage # uniquement ces contrôles
scripts/ci.sh --skip build          # tout sauf build
scripts/ci.sh --help
```

Prérequis : `python3` (pour `check_thresholds.py`). Les autres outils sont
détectés ; un outil absent donne un **avertissement** et marque le contrôle
`not_run` (jamais un faux succès).

## Sorties (`reports/`) — contrat § 10 de la spec

| Contrôle | Sortie |
|---|---|
| Tests | `reports/junit/*.xml` (JUnit) |
| Couverture | `reports/coverage/` (Cobertura XML, lcov, JaCoCo XML ou coverage.py JSON) |
| Analyse de code, dépendances, conteneurs, secrets | `reports/security/*.sarif` (SARIF 2.1.0) |
| Lint | `reports/lint/*.txt` + code de sortie |
| Synthèse machine | `reports/summary.json` |

`reports/summary.json` suit le schéma :

```json
{
  "ts": "2026-10-11T11:40:00Z",
  "controls": {
    "lint": "pass | fail | not_run",
    "tests": "pass | fail | not_run",
    "coverage": "pass | fail | not_run",
    "sast": "pass | fail | not_run",
    "deps": "pass | fail | not_run",
    "secrets": "pass | fail | not_run",
    "build": "pass | fail | not_run"
  },
  "coverage_pct": 87.5,
  "vulns": { "critique": 0, "haute": 0, "moyenne": 0, "basse": 0 },
  "blocking": false
}
```

`coverage_pct` et les compteurs `vulns` valent `null` si la valeur n'est pas
mesurée (aucune donnée inventée).

## Seuils

Lus dans `sdlc.config.yaml` (§ 4) :

- `ci.coverage_min` : couverture minimale (pourcentage). Défaut `80`.
- `ci.block_on` : sévérités bloquantes. Valeurs `critique | haute | moyenne | faible`.
  Défaut `[critique, haute]`. Note : `faible` est le synonyme de `basse` ; le
  résumé machine normalise en `basse`.

`yq` est utilisé s'il est installé ; sinon une lecture simple par `grep`/`sed`
s'applique (limite : seuls les scalaires de premier niveau sont lus de façon
fiable). Les valeurs peuvent être surchargées par `SDLC_COVERAGE_MIN` et
`SDLC_BLOCK_ON`.

## Mapping des sévérités SARIF

Voir l'en-tête de `check_thresholds.py`. En résumé :

- propriété `security-severity` (0–10) prioritaire : `>= 9` critique, `>= 7` haute,
  `>= 4` moyenne, sinon basse ;
- à défaut, niveau SARIF : `error` → haute, `warning` → moyenne, `note` / `none` → basse.

## Tests unitaires

```sh
python3 -m unittest discover -s .sdlc/templates/scripts/tests -v
```

Les jeux d'essai couvrent les quatre formats de couverture et un SARIF mêlant
`security-severity` et niveaux.
