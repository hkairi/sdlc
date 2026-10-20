# Pipeline Jenkins

## Quand le choisir

Quand la CI retenue est un serveur **Jenkins** (`ci.tool: jenkins` dans
`sdlc.config.yaml`), par exemple en environnement auto-hébergé ou restreint.

## Où copier le fichier

Copier `Jenkinsfile` **tel quel** à la **racine** du projet (ou à un chemin
configuré dans le job). Créer un job de type **Pipeline** et renseigner ce
chemin.

Ajouter `reports/` au `.gitignore`.

## Secrets attendus

À déclarer dans **Manage Jenkins > Credentials** :

| Identifiant | Usage |
|---|---|
| `{{credential-id-deploiement}}` | Jeton ou couple identifiant/mot de passe de déploiement (utilisé via `credentials(...)`). |

## Adaptation

1. Remplacer les marqueurs `{{…}}` (agent, identifiant d'identifiant, responsables
   du go/no-go, commandes, branche principale).
2. Le déploiement en production est rendu **manuel et protégé** par l'étape
   `input`, qui exige la validation explicite d'un `submitter` (responsable du
   gate `go_no_go`). Sans validation, le pipeline reste en pause.
3. Le stage de contrôles appelle uniquement `scripts/ci.sh`.
4. `python3` doit être présent sur l'agent (requis par `check_thresholds.py`).
5. Les rapports sont publiés par `junit` (résultats de tests) et
   `archiveArtifacts` (dossier `reports/` complet).

## Enchaînement

contrôles → build → préproduction → tests de bout en bout → **production
(manuelle via `input`, protégée par `submitter`)**.
