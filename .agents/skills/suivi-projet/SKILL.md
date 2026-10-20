---
name: suivi-projet
description: Génére et met à jour le tableau de bord projet autonome (docs/suivi-projet.html) : collecte les sources du projet (sdlc.config.yaml, reports/ couverture/JUnit/SARIF, openspec/, docs/suivi/state.json, journaux, incidents, documents Markdown) dans docs/suivi/project-data.json et docs/suivi/docs-data.json, puis génère une page HTML unique (onglets Vue d'ensemble, Features, Qualité, Sécurité, Documentation, Déploiements, Agents IA, lecteur Markdown embarqué). Le tableau de bord s'affiche en un coup d'œil : avancement des features et phases, couverture et seuils, vulnérabilités bloquantes, recette, incidents, coûts par feature. Utiliser dès que l'utilisateur demande un « tableau de bord projet », un « suivi projet », un « dashboard » de bout en bout, une « vue d'ensemble de l'avancement », ou de « mettre à jour / régénérer le suivi projet » après une tâche, des contrôles, une recette, un déploiement ou à un gate.
---

# Tableau de bord projet (`suivi-projet`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

Produit et tient à jour `docs/suivi-projet.html` : une page HTML **autonome** (aucun serveur requis,
markdown-it embarqué) qui rassemble l'avancement, la qualité, la sécurité, la documentation, les
déploiements et l'activité des agents. L'état de référence vit dans les fichiers du projet ; le
tableau de bord est un **rendu** — il porte la mention « fichier généré, ne pas modifier ».

## Quand l'utiliser

- Créer ou régénérer le tableau de bord d'un projet installé dans le framework.
- Après **chaque tâche** terminée ou bloquée, après les **contrôles 5b** (`scripts/ci.sh`), après
  la **recette**, après un **déploiement**, et à **chaque gate** (spec freeze, recette, go/no-go).
- Quand l'orchestrateur a besoin d'une vue consolidée pour un point d'avancement ou au client.

Deux principes non négociables :

1. **Rien n'est inventé.** Une donnée absente ou nulle s'affiche « non mesuré » ; aucune valeur par
   défaut n'est fabriquée. Les graphiques concernés sont masqués.
2. **Markdown est la source, HTML est un rendu.** On régénère, on n'édite pas le HTML à la main.

## Commandes

Depuis la racine du projet :

```bash
# 1. Collecter les sources (écrit les JSON et un instantané d'historique).
python3 .agents/skills/suivi-projet/scripts/collect.py .

# 2. Générer le tableau de bord (dashboard.file de sdlc.config.yaml, défaut docs/suivi-projet.html).
python3 .agents/skills/suivi-projet/scripts/generate.py . --open
```

- `collect.py [RACINE]` — la racine est la racine du projet (défaut : répertoire courant).
- `generate.py [RACINE] [--out FICHIER] [--template GABARIT] [--open]` — `--out` force la sortie,
  `--open` ouvre/affiche le chemin final.
- **Toujours collecter avant de générer** : `generate.py` lit `docs/suivi/project-data.json` et
  `docs/suivi/docs-data.json`.

### Mode live (lecture des documents hors-ligne)

En `file://` le navigateur ne peut pas lire les autres fichiers : le lecteur Markdown utilise la
version embarquée. Pour la version live (documents toujours à jour, liens `.md` résolus) :

```bash
python3 -m http.server 8000
# puis ouvrir http://localhost:8000/docs/suivi-projet.html
```

## Sources lues par `collect.py`

| Source | Usage |
|---|---|
| `sdlc.config.yaml` | rôles, confidentialité, seuils (`ci.coverage_min`, `ci.block_on`), cibles de déploiement, `dashboard.file` / `embed_max_kb`. |
| `reports/summary.json` | s'il existe : `coverage_pct`, `vulns`, `blocking`, `controls` (état de CI). Sinon calcul depuis les rapports bruts. |
| `reports/coverage/` | Cobertura XML, lcov, JaCoCo XML, coverage.py JSON. |
| `reports/junit/*.xml` | total, échecs, ignorés, durée. |
| `reports/security/*.sarif` | constats, sévérités (`security-severity` puis `level`), sources. |
| `reports/lint/*.txt` | nombre d'anomalies. |
| `openspec/changes/*/` et `.../archive/` | comptage des tâches (`tasks.md`) ; changes en cours non déclarés = features dérivées. |
| `docs/suivi/state.json` | features, actions requises, environnements (voir `references/state-format.md`). |
| `docs/journal/runs.jsonl`, `deploys.jsonl` | activité et coûts par feature/agent ; historique des déploiements. |
| `docs/incidents/*.md` | incidents (titre, statut, date depuis un en-tête simple). |
| `docs/architecture/*.html` | schémas d'architecture (vignette = `.png` de même nom s'il existe) ; hors de ce dossier, aucun schéma n'est listé. |
| `.md` de `docs/` et `openspec/` | lecteur Markdown embarqué, dans la limite `dashboard.embed_max_kb` (au-delà : les plus récents d'abord, avec avertissement). |

## Sorties

- `docs/suivi/project-data.json` — données normalisées du tableau de bord, dont `current`
  (`coverage_pct`, `vulns`, `tests`) pour les valeurs courantes indépendamment de la longueur de
  l'historique.
- `docs/suivi/docs-data.json` — documents Markdown embarqués (+ avertissements de collecte).
- `docs/metrics/history.jsonl` — un instantané par jour `{date, coverage_pct, vulns, tests}`
  (aucun doublon strict du même jour, aucun instantané sans mesure) ; l'instantané du jour est
  intégré à la série affichée dès le premier lancement.
- `docs/suivi-projet.html` — le tableau de bord (mention « fichier généré, ne pas modifier »).

## `docs/suivi/state.json`

Format complet et exemple : `references/state-format.md`. En résumé : `features[]` (id, name, color,
`phases` de 6 valeurs `todo|doing|done|blocked`, blocked, recette `[ok,total]` ou `null`, version,
delivered), `actions[]`, `envs[]`. Mettre ce fichier à jour **avant** de régénérer ; ne pas y mettre
de nombre de tâches (déduit d'OpenSpec).

## Après chaque progression

1. Mettre à jour `docs/suivi/state.json` (phases, recette, actions, environnements) et, le cas
   échéant, les cases de `openspec/changes/<id>/tasks.md`.
2. Relancer `collect.py` puis `generate.py`.
3. Ne jamais éditer `docs/suivi-projet.html` ni les JSON à la main : ils sont écrasés.

## Pièges

- **Collecter avant générer** : `generate.py` s'arrête si un JSON manque.
- **Pas de version live en `file://`** : servir en http pour lire les `.md` à jour.
- **Limite d'embarquement** : au-delà de `dashboard.embed_max_kb`, des documents ne sont pas
  embarqués ; l'avertissement est affiché dans l'onglet Documentation.
- **SARIF sans `security-severity`** : la sévérité retombe sur `level` (`error` → haute,
  `warning` → moyenne, `note`/`none` → basse).
- **Aucune donnée = « non mesuré »** : ne pas « corriger » en écrivant des valeurs fictives dans
  `state.json`.
- **`docs/` en lecture seule** pour un exécutant : en cas de séparation des rôles, c'est
  l'orchestrateur qui régénère le tableau de bord.
- Les fichiers `reports/` ne sont pas versionnés : un clone sans rapport affiche « non mesuré »
  jusqu'au prochain `scripts/ci.sh`.
