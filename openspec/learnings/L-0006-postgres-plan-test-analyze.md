+++
id = "L-0006"
title = "Un test de plan Postgres doit semer son volume et ANALYZE, sinon il dépend d'une base réchauffée"
kind = "pitfall"
created = "2026-10-26"
status = "active"
scope = ["engagement-api/internal/database/push_device_keepalive_test.go", "engagement-api/scripts/setup_go_test_db.sh"]
tags = ["postgres", "planner", "tests", "docker", "determinisme"]
source_change = "containerize-sdlc-verification"

[[evidence]]
cmd = "make sdlc-go-test (base engagement_backend_go_test reconstruite à zéro, test patché avec semis 500 devices + ANALYZE)"
result = "avant : FAIL TestDormantPushDevicesSelectionUsesThePartialIndex sur base fraîche ; après : PASS (3/3 sur -run TestDormantPushDevices, puis suite complète verte)"
+++

## Règle

Un test qui asserte la **forme du plan** (EXPLAIN contient tel index) doit
semer lui-même un volume réaliste **et** exécuter `ANALYZE` sur la table
avant l'EXPLAIN. Sur une base fraîche, les statistiques sont vides : le
planificateur devine, et le choix d'index dépend de ce que les runs
précédents ont laissé derrière eux.

## Pourquoi

Le 2026-10-26, `TestDormantPushDevicesSelectionUsesThePartialIndex` semait
**1 ligne** sans ANALYZE : sur la base de l'hôte, réchauffée par des mois de
runs, le planner préférait l'index partiel ; sur la base fraîche du
conteneur, il choisissait `index_push_devices_on_client_application_id_and_deactivated_at`
(qui pré-trie le GROUP BY et ne coûte rien sur une table d'une ligne). Le
test n'avait donc **jamais** été vert sur une base neuve — il validait
l'environnement, pas la requête. L'économie à reproduire est celle de la
production : beaucoup de devices actifs récents, peu de dormants, pour que
scanner l'alternative coûte plus cher que lire l'index partiel.

## Comment vérifier

```sh
# base fraîche obligatoire — c'est le cas d'échec
docker compose -f docker-compose.sdlc.yml exec db psql -U sdlc -d postgres \
  -c "drop database if exists engagement_backend_go_test"
make sdlc-go-test
# ou ciblé :
docker compose -f docker-compose.sdlc.yml exec toolbox bash -lc \
  'cd engagement-api && go test ./internal/database -run TestDormantPushDevices -count=1 -v'
```
