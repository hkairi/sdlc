---
name: suivi-taches
description: Crée et tient à jour un fichier de suivi d'avancement (un chantier ou plusieurs features en parallèle) dont l'état de référence vit dans docs/suivi/state.json (format partagé avec suivi-projet) et dont le HTML est un rendu généré — les six phases d'un projet (cadrage, planification, implémentation, validation, déploiement, clôture), le suivi tâche par tâche, les rôles (exécutant, relecteur ≠ auteur, itération de revue, escalade, prêt à commiter), et un lecteur Markdown des sources OpenSpec. Utiliser dès que l'utilisateur demande un « fichier de suivi », un « suivi d'avancement », un « suivi multi-chantiers / multi-features », un tracker/tasklist, de « suivre un projet de bout en bout / dans toutes ses phases », de « mettre à jour le suivi » après une progression, ou d'« importer un suivi HTML existant ».
---

# Suivi des tâches (`suivi-taches`)

> **Chemins.** Les emplacements viennent de la section `paths` de `sdlc.config.yaml`
> (§ 13.3 de `.sdlc/workflow-sdlc.md`) : gabarits sous `paths.templates` (défaut
> `.sdlc/templates`), spec sous `paths.spec`, livrables sous les dossiers `paths.*`
> (défauts indiqués dans cette fiche).

Tient l'avancement d'un chantier (ou de plusieurs) **tâche par tâche**, de bout en bout : les six
phases d'un projet, les lots, les tâches, les rôles et la revue. Deux principes non négociables :

1. **L'état de référence vit dans `docs/suivi/state.json`** — un format **partagé avec la skill
   `suivi-projet`** (voir [`references/state-format.md`](references/state-format.md) et
   [`references/state.schema.json`](references/state.schema.json)). Le fichier HTML n'est qu'un
   **rendu généré** : il porte la mention « fichier généré par la skill suivi-taches, ne pas
   modifier » et embarque une copie de l'état **en lecture seule**. On ne l'édite jamais à la main ;
   le navigateur ne garde qu'un *brouillon local* (localStorage), signalé comme non reporté.
2. **On met à jour après CHAQUE progression** — tâche commencée (`doing`), terminée (`done`) ou
   bloquée (`blocked`), item de phase coché — avec une note courte (ce qui a été fait, écarts,
   résultat des vérifications), en même temps que la case du `tasks.md`. Pas d'attente de fin de lot.

Deux **gabarits** : `assets/template.html` (un chantier) et `assets/template-multi.html` (plusieurs
chantiers). `render.py` choisit automatiquement : mono si une seule feature, multi sinon.

## Fichiers de la skill

```
.agents/skills/suivi-taches/
  SKILL.md
  references/state-format.md      # format commun de docs/suivi/state.json
  references/state.schema.json    # JSON Schema du même format
  scripts/generate.py             # tasks.md → fusion dans state.json → rendu HTML
  scripts/render.py               # state.json → HTML (mono/multi), embarque les .md liés
  scripts/track.py                # met à jour une tâche (un chantier) puis régénère
  scripts/track_multi.py          # idem, résolution multi-chantiers
  scripts/track_phase.py          # met à jour un item de phase puis régénère
  scripts/migrate_from_html.py    # importe un suivi HTML existant vers state.json
  scripts/state_io.py             # lecture/écriture atomique de l'état
  scripts/phases.py               # modèle des six phases (statut dérivé)
  scripts/tracking.py             # logique commune (rôles, escalade, tâches.md, rendu)
  assets/template.html            # gabarit mono
  assets/template-multi.html      # gabarit multi
  assets/reader.js                # lecteur Markdown (embarqué dans le rendu)
  assets/vendor/markdown-it.min.js# bibliothèque markdown-it (copie locale, MIT)
  assets/manifest-example.json    # modèle de manifeste multi-chantiers
  tests/                          # tests (unittest + fixtures)
```

## Créer / régénérer un suivi

```bash
# Un chantier
python3 .agents/skills/suivi-taches/scripts/generate.py \
  --out docs/suivi-<id>.html \
  --tasks openspec/changes/<id>/tasks.md \
  --title "Suivi d'avancement — <titre> · <Projet>" \
  --h1 "<titre> — fichier de suivi" \
  --eyebrow "<Projet> · <Domaine> · Suivi d'avancement" \
  --source "proposal=openspec/changes/<id>/proposal.md" \
  --source "design=openspec/changes/<id>/design.md" \
  --source "tasks=openspec/changes/<id>/tasks.md" \
  --objective "Une phrase sur le but (markdown inline : \`code\`, **gras**)."

# Plusieurs chantiers (gabarit multi)
python3 .agents/skills/suivi-taches/scripts/generate.py --out docs/suivi-multi.html \
  --tasks openspec/changes/<a>/tasks.md --tasks openspec/changes/<b>/tasks.md
python3 .agents/skills/suivi-taches/scripts/generate.py --out docs/suivi-multi.html \
  --manifest docs/suivi-multi.json      # modèle : assets/manifest-example.json
```

- Format lu : `## 1. Titre du lot` (ou `## 6bis. …`) puis `- [ ] 1.1 Texte` / `- [x] 1.2 Texte`.
  Une étiquette `**[XXX]**` en tête devient un badge de dépendance.
- **Régénérer est sans perte** : statut, date, note, historique, rôles, fichiers, critères, tests
  **et phases** déjà présents dans `state.json` sont conservés ; une case `[x]` force `done`. Les
  features déjà présentes dans l'état mais non régénérées sont conservées.
- **Rattachement d'un tasks.md** : `generate.py` rattache le tasks.md à la feature existante dont
  `tasks_file` correspond, **avant** de déduire un identifiant du chemin ; `--id <feature>` force
  le rattachement (utile quand le chemin ne permet pas de retrouver la feature).
- `--state` change le chemin de `state.json` (défaut `docs/suivi/state.json`). L'écriture est
  **atomique** (fichier temporaire puis renommage).
- **N'invente rien** : pas d'estimation, de priorité ni de fichier qui ne vienne de la source.

## Mettre à jour après chaque progression

```bash
T(){ python3 .agents/skills/suivi-taches/scripts/track.py --file docs/suivi-<id>.html "$@"; }
T 2.1 doing "Délégué le AAAA-MM-JJ." --executor codex --reviewer claude --iteration 1
T 2.1 done  "Fait : … ; vérifié : … ." --commit-message "feat(scope): …" --ready-to-commit
T 2.4 blocked "Bloquée par dépendance : … ."
```

- `done` coche la case du `tasks.md`, tout autre statut la décoche ; la note accepte du HTML court.
- Chaque appel : écrit le statut/date/note dans `state.json` (atomique), ajoute une **entrée
  d'historique** datée, puis **régénère le HTML**.
- Ne passer à `done` qu'après vérification réelle (tests/contrôles relancés soi-même).
- En zsh, une variable `$T="python3 …"` ne se découpe pas en mots : utiliser une fonction.

### Rôles et escalade (8.3)

| Option | Effet |
|---|---|
| `--executor <agent>` | exécutant de la tâche. |
| `--reviewer <agent>` | relecteur — **refusé s'il égale l'exécutant** (règle « le relecteur n'est jamais l'auteur »). |
| `--iteration <n>` | numéro d'itération de revue (1 = première revue). |
| `--commit-message "…"` | message de commit proposé (Conventional Commits). |
| `--ready-to-commit` | marque la tâche prête à commiter. |

Le script lit `organisation.max_review_iterations` dans `sdlc.config.yaml` (défaut **3**). Quand
`--iteration` dépasse ce maximum, la tâche passe automatiquement en `blocked` avec `escalated=true`
et la note le mentionne. Le HTML affiche par tâche l'exécutant, le relecteur, l'itération, un badge
« escalade » et un badge « prêt à commiter » (message de commit dans le panneau de détail), plus un
compteur « prêtes à commiter » dans l'en-tête.

## Suivre plusieurs chantiers

```bash
M(){ python3 .agents/skills/suivi-taches/scripts/track_multi.py --file docs/suivi-multi.html "$@"; }
M archive-abandoned-purchases:2.3 doing "Délégué."
M bpay:0.1 done "Fait : … ." --executor codex --reviewer claude
M auth:3.2 blocked "Contrat admin en attente."
```

- Désigner la tâche par `chantier:tâche` ; un identifiant seul est accepté s'il est unique.
- Même comportement que `track.py` (rôles, escalade, historique, case du `tasks.md`, rendu).

## Accompagner un projet dans toutes ses phases

Chaque chantier porte six phases ; le statut d'une phase est **dérivé** de ses items (ou des tâches
pour l'implémentation) : `done` si tout est fait, `blocked` si un item est bloqué, `doing` si un
item est en cours/fait, sinon `todo`. La phase en cours est la première non terminée.

| # | Phase | Objet | Items par défaut |
|---|---|---|---|
| 1 | **Cadrage** | Proposition et conception | proposition (`proposal.md`), deltas de specs (≥1 scénario), `design.md` si transversal, `openspec validate --strict`, décisions, approbation |
| 2 | **Planification** | Découpage | `tasks.md` (lots/tâches), dépendances externes, fichier de suivi généré |
| 3 | **Implémentation** | Le code | *dérivée des tâches* (X/Y, bloquées) |
| 4 | **Validation** | Preuves | contrôles relancés (0 échec), lint, typecheck, critères d'acceptation, revue, conformité aux deltas |
| 5 | **Déploiement** | Mise en prod | migrations réversibles, env/secrets, runbook, production, smoke test |
| 6 | **Clôture** | Archive et suites | archive OpenSpec, `features.md`/`architecture.md`/`runbook.md`, suivi post-déploiement, retour |

### Mettre à jour une phase

```bash
P(){ python3 .agents/skills/suivi-taches/scripts/track_phase.py --file docs/suivi-multi.html "$@"; }
P bpay:validation.tests done "Rejeu 18/18 conformes."
P bpay:deploy.migrations doing "Migration en cours d'écriture."
Q(){ python3 .agents/skills/suivi-taches/scripts/track_phase.py --file docs/suivi-<id>.html "$@"; }
Q validation.tests done "36 runs, 0 échec."
```

- Identifiant : `<phase>.<item>` (ex. `validation.tests`) ; en multi, préfixer le chantier.
- La phase `impl` est **dérivée des tâches** : la mettre à jour via `track.py` / `track_multi.py`.

### Ce que la skill attend à chaque phase

- **Cadrage** : `proposal.md` (Why / What / Impact) ; deltas `## ADDED|MODIFIED|REMOVED` avec au
  moins un `#### Scenario:` ; `design.md` seulement si transversal / dépendance externe / modèle de
  données ; `openspec validate <id> --strict` sans erreur ; **ne pas commencer l'implémentation
  avant approbation**.
- **Planification** : `tasks.md` en lots ordonnés, dépendances externes identifiées ; générer le suivi.
- **Implémentation** : après chaque tâche, `track` (statut + note factuelle + case `tasks.md`).
- **Validation** : relancer soi-même les **contrôles du projet** — `scripts/ci.sh` et les commandes
  déclarées dans `sdlc.config.yaml` (`ci.tool`) ; vérifier les critères d'acceptation et la
  conformité aux deltas ; consigner les chiffres dans la note. Ne coder aucune commande propre à un
  projet dans la skill : elles viennent de `scripts/ci.sh` / de la config.
- **Déploiement** : migrations réversibles testées up/down, variables et secrets à jour, étapes du
  runbook, déploiement, smoke test.
- **Clôture** : archiver le change (`openspec archive <id>`), mettre à jour `features.md`,
  `architecture.md`, `runbook.md`, suivre les logs/métriques, consigner les écarts.

## Importer un suivi HTML existant (migration)

```bash
python3 .agents/skills/suivi-taches/scripts/migrate_from_html.py \
  --file docs/suivi-<id>.html [--state docs/suivi/state.json] [--id <feature>] [--name "<nom>"] \
  [--change <change>] [--tasks openspec/changes/<id>/tasks.md]
```

Formats détectés : nouveau (`state-data`), multi (`feature-data`) et mono
(`data-status`/`data-updated`/note + `phase-data`). L'import ne perd rien de ce qui est présent
(statut, date, note, historique, rôles, lots, phases) ; les champs absents restent `null`. Le mono
relit aussi les **métadonnées** du HTML — `title`, `h1`, `eyebrow`, sous-titre (dans `meta`),
objectif, décisions et sources avec leurs liens (sur la feature). `--tasks <tasks.md>` recharge le
**texte complet** et le **titre court** de chaque tâche (statut, note, historique et rôles
conservés), et **enregistre `tasks_file`** dans la feature migrée : `generate.py` rattache ainsi
les régénérations suivantes à la même feature, même sans `--id`. Un résumé est affiché ; le script
n'écrit jamais le HTML.

## Lecteur Markdown

Le rendu embarque un lecteur identique à celui de `suivi-projet` : **markdown-it** embarqué depuis
`assets/vendor/markdown-it.min.js` (copie locale), **HTML brut désactivé**, rendu OpenSpec (deltas,
exigences, scénarios, mots-clés), cases à cocher, sommaire, liens `.md` relatifs ouverts dans le
lecteur. En `file://` la version **embarquée** est utilisée ; servie en `http`, la version **live**
(lecture des fichiers à jour) :

```bash
python3 -m http.server 8000   # puis ouvrir http://localhost:8000/docs/suivi-<id>.html
```

`render.py` embarque le contenu des `.md` liés : les sources de chaque feature (proposal, design,
tasks) **et** les deltas de spec du change (`openspec/changes/<change>/specs/**/*.md`).

## Lien avec `suivi-projet`

`docs/suivi/state.json` est la **source de vérité partagée**. `suivi-taches` l'écrit ; `suivi-projet`
(`collect.py`) le lit pour son tableau de bord (`docs/suivi-projet.html`). Le format complet est
documenté une seule fois dans [`references/state-format.md`](references/state-format.md) ; la
référence de `suivi-projet` y renvoie. `collect.py` tolère les deux formes de `features[].phases`
(la forme courante, objets, et la forme historique, six chaînes). Après mise à jour de l'état,
régénérer aussi le tableau de bord : `collect.py` puis `generate.py` de `suivi-projet`.

## Ce que la page offre

- **Mono** : bandeau des phases, statistiques et pastilles de lot cliquables (filtres), recherche
  plein texte, **mode focus** (un lot et/ou un statut ; Échap pour quitter, re-clic pour retirer),
  vue partageable dans l'URL (`#lot=L2&statut=doing`, survit au rechargement), cartes d'information
  **Objectif / Décisions / Procédure / Sources** réductibles (▾) et fermables (×) avec « Cartes
  masquées » pour les rouvrir et préférence mémorisée, **export / import JSON** des brouillons,
  détail par tâche (fichiers, critères, tests, historique, message de commit), badges de rôle,
  compteur « prêtes à commiter », impression/PDF, lecteur Markdown.
- **Multi** : rail de chantiers (sticky) avec sélection multiple, vue d'ensemble comparative,
  espace de travail par chantier ou par statut, panneau de détail (rôles, escalade, message de
  commit, historique), densité, filtres, impression, lecteur Markdown. Sélection, filtres et vue
  sont mémorisés dans l'URL et le navigateur.

## Vérifier un suivi généré

```bash
# JSON embarqué valide et « </ » échappé (state-data + docs-data)
python3 - <<'PY'
import json, re
h = open('docs/suivi-<id>.html', encoding='utf-8').read()
for b in ('state-data', 'docs-data'):
    m = re.search(r'<script type="application/json" id="%s">(.*?)</script>' % b, h, re.S)
    assert m and '</' not in m.group(1); json.loads(m.group(1))
assert not re.findall(r'\{\{[A-Z_]+\}\}', h)
print('ok')
PY
# scripts JS (le fichier en contient plusieurs : markdown-it, reader, app)
python3 -c "import re,sys;b=re.findall(r'<script>(.*?)</script>',open(sys.argv[1]).read(),re.S);[open('/tmp/s%d.js'%i,'w').write(x) for i,x in enumerate(b)];print(len(b),'scripts')" docs/suivi-<id>.html
for f in /tmp/s*.js; do node --check "$f"; done
```

## Tests et pièges

```bash
python3 -m unittest discover -s .agents/skills/suivi-taches/tests
```

- Quand un agent délégué ne doit pas toucher `docs/`, c'est l'orchestrateur qui met le suivi à jour
  après relecture — le préciser dans le brief.
- Ne pas éditer le HTML ni les brouillons comme source de vérité : seul `state.json` fait foi.
- Le HTML embarque du JSON : passer par les scripts (qui échappent « </ ») plutôt que d'injecter à
  la main. `tasks_file` est relatif à la racine du dépôt.
- La phase `impl` est dérivée : ne pas la cocher directement.
- Un relecteur égal à l'exécutant est refusé ; au-delà de `max_review_iterations`, la tâche est
  escaladée automatiquement (statut `blocked`).
