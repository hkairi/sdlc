# ADR-003 — Application locale, écoute 127.0.0.2, sans authentification

## Statut

Accepté — 2026-10-20.

Remplacé par : —

## Contexte

La Console est un outil personnel d'orchestrateur, exécuté sur le poste de travail. Elle
manipule des données de projet sensibles (commits, revues, décisions, logs) mais ne doit pas
exiger une infrastructure d'authentification pour le MVP.

L'utilisateur a choisi : **aucune authentification**, écoute sur **127.0.0.2** pour le moment.
La revue contradictoire a signalé que l'absence d'auth rend CSRF inopérant et expose au
**DNS rebinding** : un site distant peut viser `127.0.0.2` et tenter un POST.

## Décision

- Écoute par défaut sur **127.0.0.2:8765**, dans la boucle locale.
- **Refus de tout bind hors `127.0.0.0/8`** (`0.0.0.0`, `::`, IP LAN, hostname), avec un
  message explicite. Un flag `--allow-lan` ne sera ajouté qu'avec un token (hors MVP).
- **Aucune authentification** en MVP ; l'acteur des décisions est le poste local, et l'audit
  le mentionne explicitement (« décision depuis le poste local, non authentifiée »).
- **Validation stricte de l'en-tête `Host`** : uniquement `127.0.0.2:8765`, `localhost:8765`
  et l'équivalent IPv6 loopback si activé.
- **Refus des `Origin`/`Referer` externes** sur les méthodes d'écriture.
- **CORS désactivé** ; le frontend est servi par le même origin.
- **CSRF** : jeton d'écriture pour les formulaires, même sans session, pour éviter les POST
  navigateur non désirés. Le jeton est obtenu via `GET /api/csrf` et transmis dans l'en-tête
  `X-SDLC-CSRF` ; sans lui, la requête reçoit `403`.
- **Content-Type JSON obligatoire** pour les écritures.
- Journal d'audit de toutes les actions d'écriture.
- **WSL2** : `127.0.0.2` n'est pas garanti depuis l'hôte Windows en mode NAT ; le guide
  d'installation documente le mode réseau miroir ou l'usage d'un navigateur dans WSL.

## Conséquences

### Positives

- Installation et usage immédiats, sans compte ni mot de passe.
- Aucune donnée d'authentification à stocker ou à fuiter.
- Surface réseau quasi nulle : boucle locale uniquement.
- DNS rebinding et POST cross-origin bloqués par `Host`/`Origin`.

### Négatives

- Tout processus local peut appeler l'API : la sécurité repose sur le poste.
- Pas de non-répudiation : l'acteur est déclaratif.
- Pas de multi-utilisateur ni de partage LAN.
- Un token sera nécessaire avant toute exposition réseau.

## Alternatives envisagées

| Alternative | Avantages | Inconvénients | Raison du rejet |
|---|---|---|---|
| Token local dès le MVP | Non-répudiation partielle, protège le LAN | Friction, stockage du token, rotation | L'utilisateur a demandé aucune auth pour le moment |
| Mot de passe + session | Plus classique | Gestion de session, mot de passe, CSRF complet | Surdimensionné pour un outil local |
| Reverse proxy + mTLS | Fort | Infrastructure, certificats | Hors MVP local |
| Bind `0.0.0.0` avec firewall | Accès LAN | Risque d'exposition, pas de contrôle applicatif | Contraire au principe local |

## Références

- Cahier des charges §10, §11, §12 : [`../00-cadrage/cahier-des-charges-web.md`](../../00-cadrage/cahier-des-charges-web.md)
- Revue contradictoire, constats sécurité : [`../00-cadrage/revue-cahier-des-charges-web.md`](../../00-cadrage/revue-cahier-des-charges-web.md)
- Analyse de menaces : [`../menaces.md`](../menaces.md)

---

*Date de proposition : 2026-10-20 — Date d'acceptation : 2026-10-20*
