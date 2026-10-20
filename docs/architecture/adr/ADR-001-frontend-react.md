# ADR-001 — Frontend React 19 + TypeScript + Vite

## Statut

Accepté — 2026-10-20.

Remplacé par : —

## Contexte

La Console SDLC doit rendre **12 vues riches** : tableaux filtrables, graphes, cartes
d'activité, matrices de risque, lecteur Markdown, formulaires de décision, logs en temps réel.
La maquette validée `docs/mockup-framework.html` définit la structure, les états et les
interactions.

Le framework impose par ailleurs : application locale, pas de lock-in IDE, pas de dépendance
à un service tiers, interface en français, accessibilité RGAA AA. L'équipe connaît React et
TypeScript ; le build peut être fait une fois et servi par le backend.

## Décision

- **React 19 + TypeScript + Vite** pour l'interface.
- **React Router** pour les 12 routes, **TanStack Query** pour les appels API et le cache,
  **composants SVG/CSS** pour les graphiques (bibliothèque légère à confirmer par mesure).
- Le build est **embarqué** et servi par FastAPI ; **Node 22+ n'est requis qu'au build**,
  jamais au runtime.
- Les états (chargement, vide, erreur, périmé, désactivé) sont des composants communs.
- Accessibilité : navigation clavier, `aria-live` pour le SSE, contraste AA, thèmes clair et
  sombre, `prefers-reduced-motion`.

## Conséquences

### Positives

- Écosystème riche, composants et outillage matures.
- Typage fort des contrats API, refactoring sûr.
- Build statique simple à servir localement, sans runtime Node.
- Correspondance directe avec la maquette et les 12 vues.

### Négatives

- Chaîne de build supplémentaire (Node, `npm`, bundler).
- Taille de bundle à surveiller ; budget à définir.
- Deux langages (Python/TypeScript) à maintenir.
- Risque de sur-ingénierie pour des vues simples ; limiter les dépendances.

## Alternatives envisagées

| Alternative | Avantages | Inconvénients | Raison du rejet |
|---|---|---|---|
| HTMX + Jinja | Pas de build, très léger, proche du rendu serveur | Interactions riches et temps réel plus difficiles, moins de composants | Les 12 vues et le SSE demandent une vraie couche cliente |
| Svelte + SvelteKit | Bundle plus petit, syntaxe concise | Écosystème plus restreint, moins de recul sur les 12 vues | Compétence et écosystème React plus sûrs |
| Vue 3 | Bon équilibre, écosystème solide | Moins aligné avec l'équipe | Préférence React confirmée le 2026-10-20 |

## Références

- Cahier des charges §12 et §17 : [`../00-cadrage/cahier-des-charges-web.md`](../../00-cadrage/cahier-des-charges-web.md)
- Maquette : [`../../mockup-framework.html`](../../mockup-framework.html)
- Revue contradictoire : [`../00-cadrage/revue-cahier-des-charges-web.md`](../../00-cadrage/revue-cahier-des-charges-web.md)

---

*Date de proposition : 2026-10-20 — Date d'acceptation : 2026-10-20*
