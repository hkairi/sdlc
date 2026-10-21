# Audit d'accessibilité — 12 vues

> Audit statique et tests de composants du 21 octobre 2026. Référentiels : RGAA 4.1 AA
> et WCAG 2.2 AA. Les couleurs ont été mesurées sur les jetons CSS des thèmes clair et
> sombre ; les composants sont couverts par les tests Vitest du dossier
> `apps/console/web/src`.

## Synthèse

| Vue | Navigation clavier | Titre et région | Tableaux / équivalent textuel | Annonces dynamiques | Statut |
|---|---|---|---|---|---|
| Vue d'ensemble | liens et contrôles natifs | `h2`, section nommée | KPI et pipeline textuels | `role="status"` du suivi | conforme |
| Features & tâches | filtres, boutons, détail | `h2`, section nommée | tableaux avec `caption` | `aria-live` | conforme |
| Gates & qualité | consultation seule | `h2`, section nommée | tableau avec `caption` | `aria-live` | conforme |
| Revue indépendante | consultation seule | `h2`, section nommée | tableaux avec `caption` | `aria-live` | conforme |
| Déploiements | sélecteur, pagination | `h2`, section nommée | deux tableaux avec `caption` | `aria-live` | conforme |
| Équipe | consultation seule | `h2`, section nommée | tableaux avec `caption` | `aria-live` | conforme |
| Processus | consultation seule | `h2`, section nommée | listes et libellés textuels | `aria-live` | conforme |
| Sécurité | consultation seule | `h2`, section nommée | tableau avec `caption` | `aria-live` | conforme |
| Performance & données | consultation seule | `h2`, section nommée | tableau avec `caption` | `aria-live` | conforme |
| Agents IA | filtres, boutons, journal | `h2`, section nommée | tableau avec `caption` | `aria-live` du journal | conforme |
| Documentation | boutons Lire/Régénérer | `h2`, section nommée | tableau avec `caption` | `aria-live` | conforme |
| Configuration | consultation seule | `h2`, section nommée | tableau avec `caption` | `aria-live` | conforme |

## Points vérifiés

- **Lien d'évitement** « Aller au contenu principal » avant `main#main-content`.
- **Focus visible** : contour de 3 px sur `a`, `button`, `select`, `input` et le journal.
- **Clavier** : contrôles natifs (`button`, `select`, `input`), aucun gestionnaire de clic
  sur un élément non focusable.
- **Équivalents textuels** : les KPI, verdicts, gates et zones affichent une valeur texte ;
  aucune information n'est portée uniquement par la couleur (le libellé du verdict est
  toujours présent).
- **Tableaux** : chaque tableau possède un `caption` et des en-têtes `th scope="col"`.
- **SSE** : `RunLog` annonce les mises à jour dans `aria-live="polite"` et ne déplace pas
  le focus ; test `RunLog.test.tsx`.
- **Mouvement** : `@media (prefers-reduced-motion: reduce)` réduit animations et transitions.
- **Langue** : `index.html` déclare `lang="fr"`.

## Contraste mesuré (AA ≥ 4,5:1)

| Paire | Thème clair | Thème sombre |
|---|---:|---:|
| Texte principal / panneau | 15,65:1 | 14,14:1 |
| Texte atténué / panneau | 5,47:1 | 7,43:1 |
| Marque / panneau | 8,86:1 | 5,55:1 |
| Erreur / panneau | 7,29:1 | 8,39:1 |
| Avertissement / panneau | 5,93:1 | 10,32:1 |

## Limites

Cet audit est statique et couvert par les tests de composants ; il ne remplace pas un audit
assisté par lecteur d'écran sur un navigateur réel. Les quatre vues auparavant absentes de
l'interface (Gates, Revue, Équipe, Processus) ont été ajoutées avant cet audit.
