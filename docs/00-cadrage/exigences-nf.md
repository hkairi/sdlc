# Exigences non fonctionnelles — Console SDLC

> Dérivées du cahier des charges [`cahier-des-charges-web.md`](cahier-des-charges-web.md)
> et de la revue [`revue-cahier-des-charges-web.md`](revue-cahier-des-charges-web.md).
> Les valeurs sont des **cibles proposées**, pas des mesures.

## 1. Performance

| Indicateur | Objectif | Mesure | Responsable de la mesure |
|---|---|---|---|
| Vue d'ensemble | < 1,5 s sur 100 k commits / 1 M lignes | Test de charge sur jeu de démonstration | Équipe Console |
| Vue projet multi-dépôts | < 2 s sur 5 dépôts / 100 k commits | Test de charge | Équipe Console |
| Liste paginée | < 500 ms | Mesure API | Équipe Console |
| Ingestion incrémentale | 10 k commits < 60 s par dépôt | Benchmark reproductible | Équipe Console |
| Démarrage | < 2 s à froid | Mesure | Équipe Console |
| Mémoire | < 512 Mo pour 100 k commits | Mesure | Équipe Console |

**Dégradation gracieuse** : au-delà des volumes cibles, l'interface affiche un avertissement
« dépôt volumineux, mesures prêtes », pagine et n'essaie pas de tout charger.

## 2. Sécurité

| Exigence | Niveau | Justification | Vérification |
|---|---|---|---|
| Écoute uniquement sur `127.0.0.0/8` | Obligatoire | Application locale sans auth | Test paramétré : `0.0.0.0`, `192.168.1.10`, `::`, hostname refusés |
| Validation stricte de l'en-tête `Host` | Obligatoire | Prévenir le DNS rebinding | Test avec `Host` externe |
| Refus des requêtes `Origin`/`Referer` externes | Obligatoire | Prévenir les POST cross-origin | Test navigateur + curl |
| CSRF sur les actions d'écriture | Obligatoire | Décisions, lancement d'agent, purge | Jeton via `GET /api/csrf`, en-tête `X-SDLC-CSRF`, 403 sinon |
| XSS : Markdown et logs rendus en texte échappé | Obligatoire | Contenu externe non fiable | Test XSS, CSP |
| Injection SQL | Obligatoire | Requêtes paramétrées uniquement | Revue + tests |
| Path traversal | Obligatoire | Ingestion de chemins | Refus `..`, chemins résolus |
| Aucun secret en base ni en log ni en export | Obligatoire | Jetons GitHub/GitLab | Test avec faux jeton sur logs, exports et `stats_json` |
| Environnement des agents purgé des jetons | Obligatoire | Éviter l'exfiltration | Test d'environnement |
| Audit à chaîne de hachage par projet | Obligatoire | Traçabilité des décisions | Test d'intégrité au démarrage et après purge |
| Acteur local non authentifié documenté | Obligatoire | Pas de non-répudiation en MVP | Mention UI + audit |

## 3. Accessibilité

| Référentiel | Niveau cible | Périmètre concerné |
|---|---|---|
| RGAA 4.1 | AA | Les 12 vues, formulaires, tableaux, graphiques |
| WCAG 2.2 | AA | Navigation clavier, contraste, focus, texto alternatif |
| `aria-live` | Priorité polite | Logs SSE, ingestion, changements de gate |

Exigences : navigation clavier complète, focus visible, aucune information portée par la
seule couleur, tableaux avec `caption`, graphiques avec équivalent textuel, thèmes clair et
sombre contrastés, `prefers-reduced-motion` respecté.

## 4. Confidentialité et conformité

- **Données traitées** : identités des contributeurs (nom, email, comptes GitHub/GitLab),
  commits, MR, revues, approbations, décisions et dérogations, logs de runs, documents.
- **Localisation** : uniquement sur le poste ; aucune télémétrie, aucun transfert sortant
  par défaut.
- **Base légale** : à confirmer avec le client (exécution du contrat ou intérêt légitime) ;
  aucune base légale n'est inventée.
- **Durée de conservation** : 12 mois par défaut pour les données opérationnelles,
  configurable par table ; l'audit est exclu de la purge automatique et purgé sur décision
  explicite avec ancrage.
- **Minimisation** : seules les données des dépôts déclarés sont ingérées ; pas de profil
  comportemental, pas de données hors projet.
- **Droits** : export JSON/CSV, purge par projet, suppression d'un dépôt avec règle explicite.
- **Mesures techniques** : boucle locale, aucun secret en base, redaction des logs, audit
  haché, sauvegarde chiffrée par l'OS ou l'outil de sauvegarde.
- **Limite assumée** : SQLite stocke les données en clair ; un poste compromis expose la
  base. Le chiffrement disque relève de l'OS en MVP.

## 5. Exploitabilité

| Sujet | Exigence | Outillage |
|---|---|---|
| Logs | Logs structurés, rotation, redaction | Journal local |
| Audit | Chaîne de hachage, contrôle d'intégrité | `sdlc-console doctor` |
| Sauvegarde | Sauvegarde globale vérifiée, restauration testée | `backup`, `restore` |
| Rétention | Purge 12 mois, journalisée, avec confirmation ; audit exclu, logs inclus | `purge` |
| Diagnostic | Versions, chemins, port, schéma, jetons, quotas | `doctor`, `/api/health` |
| Migration | Sauvegarde avant migration, refus si schéma plus récent | Alembic |
| Supervision | Âge de la dernière sauvegarde et de la dernière ingestion | Vue d'ensemble |

## 6. Compatibilité

| Cible | Versions supportées | Exclusions |
|---|---|---|
| macOS | 14+ | — |
| Linux | Ubuntu 22.04+, Debian 12+ | — |
| Windows | 11 via WSL2 | Natif non garanti en MVP |
| Python | 3.12+ | 3.9–3.11 |
| Node | 22+ (build uniquement) | Runtime Node |
| SQLite | 3.45+ | Versions antérieures |
| Navigateurs | Chrome, Firefox, Safari (2 dernières versions) | IE, anciens Edge |

Trousseau OS : macOS Keychain, Linux libsecret, Windows Credential Manager (WSL à valider) ;
fallback variable d'environnement documenté comme usage de développement.

**WSL2** : `127.0.0.2` n'est pas garanti depuis le navigateur de l'hôte Windows en mode NAT.
Le guide d'installation documente le mode réseau miroir ou l'usage d'un navigateur dans WSL ;
un test de matrice vérifie la joignabilité.

## 7. Exigences de maintenance

- Couverture de tests minimale : **80 %**.
- Lint et typecheck verts : `ruff`, `mypy`, `eslint`, `tsc`.
- Documentation obligatoire : README, guide d'installation, guide utilisateur, runbook, ADR,
  analyse de menaces.
- Dette technique : aucune vulnérabilité haute ou critique ouverte ; dérogations datées.
- Tests de non-régression sur les formules de calcul (équipe, processus, gates).
- Revue croisée : relecteur ≠ auteur, autre modèle si disponible.

---

*Validé par : l'utilisateur (responsable humain) — Date de validation : 2026-10-20.*
