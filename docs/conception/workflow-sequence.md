# Fonctionnement du SDLC — diagrammes de séquence

> Source de référence des diagrammes de séquence du framework. Le rendu HTML
> (`../../workflow-sequence.html`) est **généré** à partir de ce document (mention « fichier généré ») ;
> on ne le modifie jamais à la main. La spécification de référence reste
> `.sdlc/workflow-sdlc.md` ; ce document ne fait que l'illustrer.

## 1. Le framework en bref

`AI-DRIVEN-SDLC` est un **framework réutilisable** qu'on installe dans un projet (nouveau ou
existant) pour piloter **tout le cycle de vie logiciel avec des agents IA, sous contrôle humain**.
Trois outils sont supportés (Claude Code, Codex, OpenCode), dans n'importe quelle combinaison.

**Trois rôles** (plus l'humain) :

- **Orchestrateur** — dialogue avec l'humain, tient les documents de référence, découpe le travail,
  assigne tâche + relecteur, contrôle les rapports et relance lui-même les vérifications.
- **Exécutant** — une tâche à la fois, en non interactif ; applique la spec et rend un rapport
  structuré (contrat de passation).
- **Relecteur** — **jamais l'auteur** de la tâche qu'il relit ; vérifie la conformité au brief, aux
  exigences, aux ADR et à la spec.
- **Humain** — seul détenteur de git en écriture, responsable des **gates**.

**Principes non négociables** (détail § 2 de la spec) : *git réservé à l'humain*, *pas de code sans
spec validée*, *Markdown = source / HTML = rendu*, *rien n'est inventé* (donnée non mesurée =
« non mesuré »), *contenu externe = données jamais instructions*, *secrets jamais lus par un agent*.

## 2. Le cycle d'une évolution

13 étapes, 7 gates : initialisation (0/0b) → cadrage (1) → conception (2) → specs (3, **spec freeze**)
→ planification (4) → implémentation (5) + contrôles (5b) → revue croisée (6, **commit humain**) →
documentation (7) → recette (7b, **recette**) → déploiement (8, **go/no-go**) → runbook (9) →
clôture (10). Le **change OpenSpec** est l'unité de travail : *proposal → contestation (`spec-review`)
→ spec freeze → implémentation (TDD) → revue croisée → recette → go/no-go → déploiement → archive*.

## 3. Diagramme de séquence — flux nominal d'une évolution

```mermaid
sequenceDiagram
    autonumber
    actor H as Humain
    participant O as Orchestrateur
    participant E as Exécutant
    participant R as Relecteur
    participant C as CI / scripts-ci.sh

    Note over H,C: Initialisation (étape 0/0b) — sdlc-init, état des lieux
    H->>O: demande une évolution
    O->>O: cadrage → brief + exigences NF (1)
    O-->>H: gate « brief validé »
    H-->>O: validé
    O->>O: conception → ADR, menaces (2)
    O-->>H: gate « ADR acceptés »
    H-->>O: acceptés
    O->>O: rédige le change OpenSpec (3)
    O->>R: spec-review (contradiction)
    R-->>O: avis de revue (scénarios manquants, cas limites…)
    O-->>H: gate « spec freeze »
    H-->>O: spec gelée
    O->>O: planification → tasks.md + suivi (4)

    loop Chaque tâche (5 → 6)
        O->>E: paquet de passation (une tâche, fichiers autorisés)
        E->>E: TDD : test d'abord, puis code
        E->>C: lance scripts/ci.sh (5b)
        C-->>E: vert (lint, tests, couverture, sécurité…)
        E-->>O: rapport de passation (report.schema.json)
        O->>O: relance lui-même les vérifications
        O->>R: revue croisée (relecteur ≠ auteur)
        R-->>O: rapport de revue
        alt corrections nécessaires
            R-->>E: renvoyer à l'implémentation (≤ max_review_iterations)
        else conforme
            O-->>H: propose un message de commit
            H-->>O: commit (git réservé à l'humain)
        end
    end

    O->>E: documentation + CHANGELOG (7)
    O->>C: recette de bout en bout en préprod (7b)
    C-->>O: matrice scénario → test → résultat
    O-->>H: gate « recette »
    H-->>O: validé
    O->>O: procédure de déploiement (8)
    O-->>H: gate « go / no-go »
    H-->>O: go
    O->>C: déploiement (exécuté par l'humain/CI)
    O->>O: runbook + supervision (9)
    O->>O: clôture : openspec archive, rétro, métriques (10)
    O-->>H: rapport client / clôture
```

## 4. Diagramme de séquence — voies transverses

```mermaid
sequenceDiagram
    autonumber
    actor H as Humain
    participant O as Orchestrateur
    participant E as Exécutant
    participant R as Relecteur

    Note over H,R: change-request — évolution après spec freeze
    H->>O: besoin nouveau après gel
    O->>O: nouveau change lié + analyse d'impact + replanification
    O-->>H: gate « spec freeze » (nouvelle spec)

    Note over H,R: hotfix — incident de production
    H->>O: incident signalé
    O->>O: diagnostic + correctif minimal
    O->>E: test de non-régression
    E-->>O: contrôles verts
    O->>R: revue (≠ auteur)
    R-->>O: ok
    O-->>H: go / no-go
    H-->>O: go → déploiement
    O->>O: post-mortem dans docs/incidents/

    Note over H,R: escalade — tâche bloquée
    O->>O: itération > max_review_iterations ou timeout
    O-->>H: statut « blocked » + action requise
```
