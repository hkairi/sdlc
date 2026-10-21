# Documentation

- [`00-cadrage/brief.md`](00-cadrage/brief.md) — brief de la Console SDLC : problème, objectifs, périmètre, risques.
- [`00-cadrage/exigences-nf.md`](00-cadrage/exigences-nf.md) — exigences non fonctionnelles : performance, sécurité, RGAA, RGPD, exploitation.
- [`00-cadrage/cahier-des-charges-web.md`](00-cadrage/cahier-des-charges-web.md) — cahier des charges de la Console SDLC locale (SQLite) : périmètre, exigences, modèle de données, gates, revue, critères d'acceptation.
- [`00-cadrage/revue-cahier-des-charges-web.md`](00-cadrage/revue-cahier-des-charges-web.md) — revue contradictoire (itération 1).
- [`00-cadrage/revue-cahier-des-charges-web-2.md`](00-cadrage/revue-cahier-des-charges-web-2.md) — revue contradictoire (itération 2, vérification des corrections).
- [`architecture/adr/README.md`](architecture/adr/README.md) — ADR 001–006 : stack, local sans auth, GitHub/GitLab multi-dépôts, runner d'agents, rétention.
- [`architecture/menaces.md`](architecture/menaces.md) — analyse STRIDE et menaces agentiques.
- [`conception/workflow-sdlc.md`](conception/workflow-sdlc.md) — spécification de référence du framework.
- [`conception/tasks.md`](conception/tasks.md) — découpage de la construction en 11 lots.
- [`suivi-framework.html`](suivi-framework.html) — fichier de suivi de la construction (46 tâches, 11 lots), **généré** : l'état de référence est [`suivi/state.json`](suivi/state.json), mis à jour avec `.agents/skills/suivi-taches/scripts/track.py --state docs/suivi/state.json …`.
- [`workflow-sdlc.html`](workflow-sdlc.html) / [`workflow-sdlc.png`](workflow-sdlc.png) — schéma du workflow.
- [`mockup-suivi-projet.html`](mockup-suivi-projet.html) — maquette validée du tableau de bord projet (données fictives).
- [`mockup-framework.html`](mockup-framework.html) — maquette complète du tableau de bord : vue d'ensemble, features, gates, revue indépendante, déploiements, **équipe** (répartition déduite de l'historique) et **processus** (git flow détecté), données fictives.
- [`mockup-dashboard-sdlc.html`](mockup-dashboard-sdlc.html) — maquette de la console produit « My AI powered SDLC » (données fictives) : organisation (équipes, projets, membres et rôles), travail (features, tickets, changes OpenSpec) et pilotage (avancement, runs d'agents, qualité, coûts, incidents).

- [`installation.md`](installation.md) — installation `uv`/`pipx`, build frontend embarqué, WSL2.
- [`ops/runbook.md`](ops/runbook.md) — runbook d'exploitation et escalades.
- [`recette/accessibilite.md`](recette/accessibilite.md) — audit d'accessibilité des 12 vues.
