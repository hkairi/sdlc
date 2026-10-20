# Intégration dans un Jenkins existant (`ci.mode: integrate`)

> Extrait à **insérer** dans le `Jenkinsfile` existant. Ne rien retirer : on ajoute seulement un
> stage qui appelle `scripts/ci.sh`.

## Quand l'utiliser

Quand `ci.mode: integrate` et qu'un `Jenkinsfile` (ou un pipeline de job) est **déjà** en place.
On ne remplace pas le pipeline ; on y ajoute les contrôles uniques.

## Prérequis

- `scripts/ci.sh` et `scripts/check_thresholds.py` installés par la skill `ci-setup` (copies de
  `.sdlc/templates/scripts/`).
- `python3` présent sur l'agent.
- Les commandes existantes fournies par `SDLC_<CONTRÔLE>_CMD` : `ci.sh` les réutilise.

## Extrait à insérer

Ajouter un `stage` dans le bloc `stages` existant, **sans supprimer** les stages présents :

```groovy
        // Stage ajouté par le framework SDLC : contrôles uniques via scripts/ci.sh.
        stage('Contrôles SDLC') {
            steps {
                sh 'bash scripts/ci.sh'
                junit allowEmptyResults: true, testResults: 'reports/junit/*.xml'
                archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
            }
        }
```

## Variante — étape dans un stage existant

Insérer `sh 'bash scripts/ci.sh'` comme étape **supplémentaire** dans les `steps` d'un stage
existant, sans retirer les étapes actuelles.

## Vérification

```sh
bash -n scripts/ci.sh
# sur un build : le stage « Contrôles SDLC » doit s'exécuter et archiver reports/
```

Les rapports ne sont pas versionnés : `reports/` doit figurer dans `.gitignore`.
