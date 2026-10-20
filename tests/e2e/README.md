# Tests de bout en bout (`tests/e2e/`)

Tests automatisés (bibliothèque standard Python, `unittest`) qui simulent l'usage
réel du framework dans **deux projets existants**, créés dans des dossiers
temporaires sous `tests/e2e/tmp/` (supprimés en fin de test).

## Lancer

```
python3 -m unittest discover -s tests/e2e
```

Ou un seul projet :

```
python3 -m unittest tests.e2e.test_e2e.ProjetDjango -v
python3 -m unittest tests.e2e.test_e2e.ProjetNode -v
```

## Projets simulés

- **Django** : `README.md`, `AGENTS.md` et `CLAUDE.md` maison, `.gitignore`,
  `templates/` de pages HTML, `requirements.txt`, un test pytest minimal,
  `.github/workflows/ci.yml` existant, `docs/` d'un autre agencement
  (`docs/decisions/` pour les ADR).
- **Node** : `package.json` (scripts `test` et `lint`), `.gitlab-ci.yml` existant,
  `openspec/` déjà initialisé avec un change contenant un `tasks.md`.

## Ce qui est couvert (par projet)

1. `bin/sdlc-install --target … --dry-run` puis installation : aucun fichier du
   projet (README, `templates/`, CI, `docs/`, `package.json`…) n'est modifié
   octet pour octet ; `AGENTS.md` commence par le bloc `sdlc` et conserve les
   règles maison ; `CLAUDE.md` contient `@AGENTS.md` ; `.sdlc/templates` et
   `.agents/skills` existent.
2. `detect.sh` : `kind: existing`, stack, CI détectée, commandes et variables
   `SDLC_<CONTRÔLE>_CMD` (`pytest` ; `npm test` / `npm run lint`).
3. `sdlc.config.yaml` réaliste (`ci.mode: integrate`, un orchestrateur et un
   exécutant) et `render_adapters.py` : seuls les adaptateurs des outils activés,
   aucun marqueur `{{…}}` restant, `CLAUDE.md` maison non écrasé.
4. `new_adr.py` : l'ADR va dans `paths.adr` (`docs/decisions/` pour Django).
5. `scripts/ci.sh` copié depuis `.sdlc/templates/scripts/` et exécuté avec des
   `SDLC_<CONTRÔLE>_CMD` simulés (JUnit et Cobertura minimaux) :
   `reports/summary.json` cohérent, CI existante non modifiée.
6. Suivi (Node) : `suivi-taches` (`generate.py` puis `track.py`) sur le `tasks.md`
   OpenSpec, puis `suivi-projet` (`collect.py` + `generate.py`) ; HTML généré,
   JSON valides.
7. Installation une seconde fois (aucune écriture), `--upgrade` (aucun fichier
   humain écrasé), `--uninstall` (`AGENTS.md`, `CLAUDE.md`, `.gitignore`
   restaurés à l'identique, plus de `.sdlc/`).

Le dossier `tmp/` est ignoré par Git (voir `.gitignore` à la racine).
