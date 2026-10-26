+++
id = "L-0005"
title = "configs_for(env_name:) compare un String — un Symbol renvoie une liste vide"
kind = "pitfall"
created = "2026-10-26"
status = "active"
scope = ["docker-compose.sdlc.yml", "Makefile", "engagement-backend/config/database.yml"]
tags = ["rails", "database-config", "docker", "toolchain"]
source_change = "containerize-sdlc-verification"

[[evidence]]
cmd = "docker compose -f docker-compose.sdlc.yml run --rm --no-deps toolbox bash -lc 'cd engagement-backend && bundle exec rails runner \"puts ActiveRecord::Base.configurations.configs_for(env_name: :test).inspect\"'"
result = "0 config pour env_name: :test (liste vide, .first → nil) ; 1 UrlConfig env_name=test pour %q(test)"
+++

## Règle

Dans tout appel à `ActiveRecord::Base.configurations.configs_for`, passer
`env_name:` en **String** (`"test"`), jamais en Symbol (`:test`) — Rails
compare sans coercition, un Symbol ne matche rien et `.first` renvoie `nil`.

## Pourquoi

Le 2026-10-26, la cible `make sdlc-rspec` chargeait le schéma via
`configs_for(env_name: :test).first` : liste vide, `load_schema(nil, …)` a
levé `undefined method 'env_name' for nil` et rspec n'a jamais démarré. Le
piège est silencieux à la lecture — `:test` *semble* plus idiomatique — et
n'explose qu'à l'exécution. Dans un Makefile, la forme `%q(test)` évite en
outre les conflits de guillemets avec l'apostrophe englobante.

## Comment vérifier

```sh
docker compose -f docker-compose.sdlc.yml run --rm --no-deps toolbox bash -lc \
  'cd engagement-backend && bundle exec rails runner \
   "puts ActiveRecord::Base.configurations.configs_for(env_name: %q(test)).inspect"'
# => [#<ActiveRecord::DatabaseConfigurations::UrlConfig env_name=test …>]
```
