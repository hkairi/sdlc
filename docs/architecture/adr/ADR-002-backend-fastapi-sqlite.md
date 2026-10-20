# ADR-002 — Backend Python FastAPI + SQLAlchemy + SQLite

## Statut

Accepté — 2026-10-20.

Remplacé par : —

## Contexte

La Console doit ingérer des données Git, GitHub/GitLab, CI, OpenSpec et des journaux,
exposer une API locale, calculer des métriques et servir le frontend. Le framework est déjà
écrit en Python (scripts, skills, installateur) et privilégie les dépendances maîtrisées.

La contrainte utilisateur est explicite : application **locale** avec **SQLite** pour le
moment. Une migration ultérieure vers PostgreSQL doit rester possible sans réécrire le modèle.

## Décision

- **Python 3.12+**, **FastAPI**, **SQLAlchemy 2**, **Alembic**, **Pydantic v2**, **Uvicorn**.
- **SQLite 3.45+** en mode **WAL**, `foreign_keys=ON`, `synchronous=NORMAL`,
  `busy_timeout=5000`, **un seul écrivain** (file d'ingestion locale).
- Les migrations sont versionnées par Alembic ; aucun `create_all` en production.
- Le schéma est portable PostgreSQL : pas de type SQLite propriétaire, pas de requête
  spécifique non documentée.
- Le frontend construit est servi par le même processus ; pas de serveur Node au runtime.

## Conséquences

### Positives

- Un seul runtime (Python), installation simple, cohérent avec le framework.
- API typée, OpenAPI gratuit, tests faciles avec `TestClient`.
- SQLite : zéro administration, fichier unique, sauvegarde simple, parfait pour le local.
- Migration PostgreSQL préparée par SQLAlchemy/Alembic.

### Négatives

- SQLite : un seul écrivain, verrous possibles sur les longues ingestions.
- Pas de haute disponibilité ni de multi-utilisateur simultané.
- FastAPI/SQLAlchemy ajoutent des dépendances à maintenir.
- Le mode WAL doit être vérifié à chaque ouverture de connexion.

## Alternatives envisagées

| Alternative | Avantages | Inconvénients | Raison du rejet |
|---|---|---|---|
| Django + SQLite | Admin, ORM, migrations intégrés | Plus lourd, moins adapté à une API locale fine | FastAPI plus direct pour l'API et les tests |
| Flask + SQLite | Minimaliste, connu | Moins de typage, OpenAPI à ajouter | FastAPI couvre le besoin |
| Node/Express + SQLite | Un seul langage avec React | Deuxième runtime, moins aligné avec les scripts Python | Le framework est Python |
| PostgreSQL dès le MVP | Concurrence, robustesse | Administration, installation, hors contrainte « locale SQLite » | Reporté, conception compatible |

## Références

- Cahier des charges §8 et §12 : [`../00-cadrage/cahier-des-charges-web.md`](../../00-cadrage/cahier-des-charges-web.md)
- Exigences NF : [`../00-cadrage/exigences-nf.md`](../../00-cadrage/exigences-nf.md)
- Revue contradictoire : [`../00-cadrage/revue-cahier-des-charges-web.md`](../../00-cadrage/revue-cahier-des-charges-web.md)

---

*Date de proposition : 2026-10-20 — Date d'acceptation : 2026-10-20*
