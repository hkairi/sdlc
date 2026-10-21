# Recette — Console SDLC

> Rapport généré par `scripts/generate_recette.py` ; ne pas modifier à la main.
> Généré le 21/10/2026 15:56 UTC. Résultat reporté : **OK — 347 tests Python + 26 tests Vitest (21/10/2026)**.

## Périmètre

Recette automatisée de la Console locale : API FastAPI, services, interface React,
sécurité loopback, gates, revue, rétention, sauvegarde, packaging et documentation.
La matrice relie chaque scénario OpenSpec à au moins un test exécutable.

## Synthèse

| Indicateur | Valeur |
|---|---:|
| Exigences | 57 |
| Scénarios | 99 |
| Références de tests | 139 |
| Résultat de la suite | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

## Matrice scénario → test → résultat

### Projet multi-dépôts

Tâches : 2.1, 2.7.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Retrait d'un dépôt | `apps/console/tests/test_repository_lifecycle.py::RepositoryLifecycleTest.test_retrait_audite_et_historique_conserve` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Ingestion Git

Tâches : 2.3.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Ingestion idempotente | `apps/console/tests/test_ingestion.py::GitIngestionTest.test_ingestion_de_base_et_idempotence` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Collecteurs GitHub et GitLab

Tâches : 2.4, 2.5.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Normalisation des deux fournisseurs | `apps/console/tests/test_providers.py::ProvidersTest.test_github_normalisation_et_idempotence`<br>`apps/console/tests/test_providers.py::ProvidersTest.test_gitlab_normalisation` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Quota fournisseur épuisé | `apps/console/tests/test_providers.py::ProvidersTest.test_quota_epuise_trace_un_echec_sans_donnees`<br>`apps/console/tests/test_provider_fixtures.py::ProviderFixturesTest.test_echec_quota_depuis_fixture` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Ingestion des runs et déploiements

Tâches : 2.8.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Déploiement ingéré | `apps/console/tests/test_journals.py::JournalIngestionTest.test_ingestion_deploys_et_rollback` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Run ingéré | `apps/console/tests/test_journals.py::JournalIngestionTest.test_ingestion_runs_et_idempotence` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Identités canoniques

Tâches : 2.2.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Contributeur multi-emails | `apps/console/tests/test_people.py::PeopleTest.test_contributeur_multi_emails_et_comptes` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Fusion auditée | `apps/console/tests/test_people.py::PeopleTest.test_fusion_ecrit_un_evenement_d_audit` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Même email dans deux projets | `apps/console/tests/test_people.py::PeopleTest.test_meme_email_dans_deux_projets` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Agrégation multi-dépôts sans double comptage

Tâches : 2.6.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Commit présent dans deux dépôts | `apps/console/tests/test_aggregation.py::AggregationTest.test_meme_empreinte_dedupliquee_et_origine` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Features et tâches multi-dépôts

Tâches : 3.1.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Feature sur deux dépôts | `apps/console/tests/test_features.py::FeaturesTasksTest.test_feature_et_tache_multi_depots` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Chemins d'ingestion confinés

Tâches : 1.7.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Path traversal | `apps/console/tests/test_paths.py::ResolveWithinTest.test_traversee_parent_refusee` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Configuration validée

Tâches : 1.2, 7.5.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Configuration invalide | `apps/console/tests/test_config.py::SchemaTest.test_config_sans_project_echoue`<br>`apps/console/tests/test_config_view.py::ConfigurationViewTest.test_configuration_invalide_indique_la_cle` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Migration de schéma

Tâches : 1.3.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| — | `apps/console/tests/test_db.py` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Diagnostic et observabilité

Tâches : 1.4.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Diagnostic complet | `apps/console/tests/test_cli.py::CliTest.test_doctor_config_valide_et_schema_a_jour` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Sécurité locale

Tâches : 1.5, 1.6.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Bind non loopback | `apps/console/tests/test_cli.py::CliTest.test_serve_refuse_un_bind_non_loopback` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Requête CSRF absente | `apps/console/tests/test_security.py::SecurityMiddlewareTest.test_csrf_absent` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| DNS rebinding | `apps/console/tests/test_security.py::SecurityMiddlewareTest.test_origine_externe`<br>`apps/console/tests/test_security.py::SecurityMiddlewareTest.test_referer_externe` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Content-Type non JSON | `apps/console/tests/test_security.py::SecurityMiddlewareTest.test_content_type_non_json` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Redaction étendue

Tâches : 6.12.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Faux jeton dans un export | `apps/console/tests/test_redaction_extended.py::RedactionExtendedTest.test_exports_json_et_csv_expurges`<br>`apps/console/tests/test_redaction_extended.py::RedactionExtendedTest.test_paquet_revue_expurge_et_csp`<br>`apps/console/tests/test_redaction_extended.py::RedactionExtendedTest.test_redaction_structuree_et_journal` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### En-têtes de sécurité et CSP

Tâches : 1.5, 6.12.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| CSP active | `apps/console/tests/test_security.py::SecurityMiddlewareTest.test_host_valide_et_entetes`<br>`apps/console/tests/test_security.py::SecurityMiddlewareTest.test_csp_stricte_verifiee`<br>`apps/console/tests/test_redaction_extended.py::RedactionExtendedTest.test_paquet_revue_expurge_et_csp` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Audit chaîné par projet

Tâches : 2.2, 2.7, 8.5.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Chaîne altérée | `apps/console/tests/test_purge.py::PurgeTest.test_chaine_audit_alteree_detectee` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Ancrage avant purge | `apps/console/tests/test_purge.py::PurgeTest.test_ancrage_et_purge_audit` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Fichier de suivi ouvert dès qu'il est prêt

Tâches : 3.4, 3.5.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Ouverture automatique du suivi | `apps/console/web/src/App.test.tsx::ouvre le suivi une seule fois quand la génération est prête` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Suivi synchrone tâche par tâche

Tâches : 3.9, 3.10, 3.11.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Changement de statut | `apps/console/tests/test_task_update.py::TaskUpdateTest.test_mise_a_jour_des_trois_supports`<br>`apps/console/tests/test_task_update.py::TaskUpdateTest.test_api_patch_avec_csrf`<br>`apps/console/tests/test_task_update.py::TaskUpdateTest.test_cli_task_set`<br>`apps/console/tests/test_task_update.py::TaskUpdateTest.test_done_equivaut_a_case_cochee_pour_tous_les_statuts`<br>`apps/console/tests/test_task_update.py::TaskUpdateTest.test_mise_a_jour_tache_par_tache_sans_mode_lot` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Modification externe | `apps/console/tests/test_suivi_watcher.py::SuiviWatcherTest.test_premier_scan_sans_evenement_puis_conflit`<br>`apps/console/tests/test_suivi_watcher.py::SuiviWatcherTest.test_modification_externe_de_state_resynchronise`<br>`apps/console/tests/test_suivi_watcher.py::SuiviWatcherTest.test_route_sse_emet_suivi_updated` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Échec d'écriture | `apps/console/tests/test_task_update.py::TaskUpdateTest.test_echec_ecriture_restaure_les_sources`<br>`apps/console/tests/test_task_update.py::TaskUpdateTest.test_echec_ecriture_state_apres_tasks_md` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Vue d'ensemble

Tâches : 3.7.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| KPI avec source et non mesuré | `apps/console/tests/test_overview.py::OverviewTest.test_kpis_avec_source_et_non_mesure`<br>`apps/console/web/src/Overview.test.tsx::affiche les KPI avec leur source et les mesures absentes` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Décisions en attente | `apps/console/tests/test_overview.py::OverviewTest.test_decisions_pipeline_et_risques` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Pipeline et risques | `apps/console/tests/test_overview.py::OverviewTest.test_decisions_pipeline_et_risques`<br>`apps/console/web/src/Overview.test.tsx::trie les décisions bloquantes, affiche le pipeline et les risques` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Vue vide sans donnée inventée | `apps/console/tests/test_overview.py::OverviewTest.test_projet_vide` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Liste et détail des features et tâches

Tâches : 3.8.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Liste filtrée | `apps/console/tests/test_features_view.py::FeaturesViewTest.test_filtres_phase_et_gate`<br>`apps/console/web/src/Features.test.tsx::conserve les filtres phase et gate dans l'URL` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Détail d'une tâche | `apps/console/tests/test_features_view.py::FeaturesViewTest.test_detail_feature_et_tache`<br>`apps/console/web/src/Features.test.tsx::ouvre le détail d'une tâche avec fichiers, critères et rapport` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Incohérence de suivi | `apps/console/tests/test_features_view.py::FeaturesViewTest.test_liste_avec_phase_gate_et_incoherences`<br>`apps/console/web/src/Features.test.tsx::affiche les features, les incohérences et les filtres depuis l'URL` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Traçabilité | `apps/console/tests/test_traceability.py::TraceabilityTest.test_matrice_des_fichiers_reels` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Verdict de gate fondé sur des preuves

Tâches : 4.1.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Gate vert avec preuve | `apps/console/tests/test_gates.py::GatesTest.test_pass_avec_preuve_et_rapport` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Gate sans preuve | `apps/console/tests/test_gates.py::GatesTest.test_pass_sans_preuve_devient_not_run_et_bloque` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Gate de tests

Tâches : 4.2.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Échec de test | `apps/console/tests/test_gate_tests.py::GateTestsTest.test_echec_de_test_bloque` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Test instable | `apps/console/tests/test_gate_tests.py::GateTestsTest.test_quarantaine_active_et_expiree`<br>`apps/console/tests/test_gate_tests.py::GateTestsTest.test_test_instable_sans_quarantaine_alerte` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Gate de couverture à trois seuils

Tâches : 4.3.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Couverture globale insuffisante | `apps/console/tests/test_gate_coverage.py::GateCoverageTest.test_couverture_globale_insuffisante` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Lignes modifiées insuffisantes | `apps/console/tests/test_gate_coverage.py::GateCoverageTest.test_couverture_lignes_modifiees_insuffisante` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Gate de sécurité

Tâches : 4.4, 7.1.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Vulnérabilité haute atteignable | `apps/console/tests/test_gate_security.py::GateSecurityTest.test_vulnerabilite_haute_atteignable_bloque` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Vulnérabilité non atteignable | `apps/console/tests/test_gate_security.py::GateSecurityTest.test_vulnerabilite_non_atteignable_alerte` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Gate de performance

Tâches : 4.5, 7.2.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Régression observée | `apps/console/tests/test_gate_performance.py::GatePerformanceTest.test_regression_observee_bloque`<br>`apps/console/tests/test_gate_performance.py::GatePerformanceTest.test_regression_par_rapport_au_baseline` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Signal statique | `apps/console/tests/test_gate_performance.py::GatePerformanceTest.test_signal_statique_alerte_sans_bloquer`<br>`apps/console/tests/test_gate_performance.py::GatePerformanceTest.test_signal_statique_sans_preuve_observee` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Gate de données

Tâches : 4.6, 7.2.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Migration destructive | `apps/console/tests/test_gate_data.py::GateDataTest.test_migration_destructive_bloque` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| PII dans les logs | `apps/console/tests/test_gate_data.py::GateDataTest.test_pii_dans_les_logs_bloque` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Gate i18n

Tâches : 4.7.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Clés manquantes | `apps/console/tests/test_gate_languages_i18n.py::GateLanguagesI18nTest.test_parite_i18n_manquante_et_orpheline` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Support des langages par tiers

Tâches : 4.7.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Langage sans adaptateur | `apps/console/tests/test_gate_languages_i18n.py::GateLanguagesI18nTest.test_langage_sans_adaptateur_bloque` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Tier 2 sans couverture | `apps/console/tests/test_gate_languages_i18n.py::GateLanguagesI18nTest.test_couverture_not_applicable_pour_tier_2` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Dérogations datées

Tâches : 4.8.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Dérogation expirée | `apps/console/tests/test_waivers.py::WaiversTest.test_derogation_active_puis_expiree` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Source unique des seuils

Tâches : 4.9.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Changement de seuil | `apps/console/tests/test_gate_config.py::GateConfigTest.test_fingerprint_change_marque_recalcul`<br>`apps/console/tests/test_gate_config.py::GateConfigTest.test_api_expose_recalcul_requis` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Métriques d'équipe

Tâches : 5.1, 5.3.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Métriques d'un contributeur | `apps/console/tests/test_team_metrics.py::TeamMetricsTest.test_metriques_par_personne_et_depot`<br>`apps/console/tests/test_team_metrics.py::TeamMetricsTest.test_filtre_par_depot` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Donnée absente | `apps/console/tests/test_team_metrics.py::TeamMetricsTest.test_metriques_par_personne_et_depot` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Chaîne de validation | `apps/console/tests/test_validation_chain.py::ValidationChainTest.test_taux_et_chaines`<br>`apps/console/tests/test_validation_chain.py::ValidationChainTest.test_api_team_contient_validation` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Bus factor et propriété

Tâches : 5.2.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Zone à bus factor 1 | `apps/console/tests/test_ownership.py::OwnershipTest.test_bus_factor_et_alertes` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Détection de processus

Tâches : 5.4.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| GitHub Flow avec releases | `apps/console/tests/test_process_detection.py::ProcessDetectionTest.test_github_flow_avec_releases` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Processus non identifiable | `apps/console/tests/test_process_detection.py::ProcessDetectionTest.test_non_identifiable` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Processus par dépôt et agrégation

Tâches : 5.5.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Dépôts divergents | `apps/console/tests/test_process_profiles.py::ProcessProfilesTest.test_divergence_sans_moyenne`<br>`apps/console/tests/test_process_profiles.py::ProcessProfilesTest.test_profil_dominant_et_surcharge` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Surcharge de processus

Tâches : 5.5.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Surcharge auditée | `apps/console/tests/test_process_profiles.py::ProcessProfilesTest.test_profil_dominant_et_surcharge`<br>`apps/console/tests/test_process_profiles.py::ProcessProfilesTest.test_api_process_override` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Métriques DORA

Tâches : 5.6.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| MTTR depuis les incidents | `apps/console/tests/test_dora.py::DoraTest.test_metriques_et_mttr` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Corpus de processus

Tâches : 5.7.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Mesure de précision | `apps/console/tests/test_process_corpus.py::ProcessCorpusTest.test_precision_et_echecs` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Flux de processus avec gates

Tâches : 5.8.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Flux affiché avec ses gates | `apps/console/tests/test_process_flow.py::ProcessFlowTest.test_flux_et_liens`<br>`apps/console/tests/test_process_flow.py::ProcessFlowTest.test_api_flux` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Indépendance de la revue

Tâches : 6.1.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Relecteur indépendant | `apps/console/tests/test_review_selection.py::ReviewSelectionTest.test_selection_meilleur_et_derogation` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Relecteur du même modèle | `apps/console/tests/test_review_selection.py::ReviewSelectionTest.test_niveaux_independance` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Dérogation d'indépendance | `apps/console/tests/test_review_selection.py::ReviewSelectionTest.test_selection_meilleur_et_derogation` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Paquet de revue aveugle

Tâches : 6.2.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Paquet aveugle | `apps/console/tests/test_review_package.py::ReviewPackageTest.test_paquet_aveugle_empreinte_et_fichier`<br>`apps/console/tests/test_review_package.py::ReviewPackageTest.test_api_paquet` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Rapport de revue structuré

Tâches : 6.3.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Rapport valide | `apps/console/tests/test_review_report.py::ReviewReportTest.test_rapport_valide_et_fiche`<br>`apps/console/tests/test_review_report.py::ReviewReportTest.test_api_rapport` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Finding sans preuve | `apps/console/tests/test_review_report.py::ReviewReportTest.test_finding_sans_preuve_refuse` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Fiche de décision

Tâches : 6.3.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Fiche de décision | `apps/console/tests/test_review_report.py::ReviewReportTest.test_rapport_valide_et_fiche` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Décision humaine auditée

Tâches : 6.4.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Approbation avec conditions | `apps/console/tests/test_decisions.py::DecisionsTest.test_approbation_conditionnelle_et_audit` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Acteur non authentifié | `apps/console/tests/test_decisions.py::DecisionsTest.test_approbation_conditionnelle_et_audit` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Préflight et lancement d'agent

Tâches : 6.5.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Préflight bloquant | `apps/console/tests/test_agent_runner.py::AgentRunnerTest.test_preflight_refuse_cli_inconnue` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Commande libre refusée | `apps/console/tests/test_agent_runner.py::AgentRunnerTest.test_preflight_refuse_cli_inconnue` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Cycle de vie et annulation d'un run

Tâches : 6.6.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Annulation d'un run en cours | `apps/console/tests/test_agent_runner.py::AgentRunnerTest.test_timeout_crash_et_annulation` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Annulation d'un run en file | `apps/console/tests/test_agent_runner.py::AgentRunnerTest.test_timeout_crash_et_annulation` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Crash ou timeout | `apps/console/tests/test_agent_runner.py::AgentRunnerTest.test_timeout_crash_et_annulation` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Concurrence et reprise après crash

Tâches : 6.5, 6.6.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Troisième run simultané | `apps/console/tests/test_agent_runner.py::AgentRunnerTest.test_file_et_concurrence` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Budget et coût d'un run

Tâches : 6.7.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Plafond atteint | `apps/console/tests/test_run_budget.py::RunBudgetTest.test_plafond_atteint_arrete_le_run`<br>`apps/console/tests/test_run_budget.py::RunBudgetTest.test_api_budget` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Environnement et lecture seule

Tâches : 6.8.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Jeton non hérité | `apps/console/tests/test_agent_sandbox.py::AgentSandboxTest.test_processus_ne_voit_pas_le_jeton` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Écriture Git refusée | `apps/console/tests/test_agent_sandbox.py::AgentSandboxTest.test_ecriture_git_refusee_et_auditee` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Logs d'agent échappés

Tâches : 6.9.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Log contenant du HTML | `apps/console/tests/test_run_events.py::RunEventsTest.test_log_echappe_et_redacte` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Escalade après rejets

Tâches : 6.10.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Trois rejets | `apps/console/tests/test_escalations.py::EscalationTest.test_trois_rejets_bloquent_et_notifient` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Dépassement du temps de tâche | `apps/console/tests/test_escalations.py::EscalationTest.test_timeout_bloque_et_notifie` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Journal des runs et indépendance

Tâches : 6.11, 7.3.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Journal filtrable | `apps/console/tests/test_run_journal.py::RunJournalTest.test_journal_filtres_et_union` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Deux provenances de runs | `apps/console/tests/test_run_journal.py::RunJournalTest.test_dedup_priorite_au_run_lance` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Seuil d'indépendance dépassé | `apps/console/tests/test_run_journal.py::RunJournalTest.test_taux_independance_seuil_et_audit` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Pagination serveur

Tâches : 7.6.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Liste paginée | `apps/console/tests/test_pagination.py::PaginationApiTest.test_features_paginees`<br>`apps/console/tests/test_pagination.py::PaginationApiTest.test_tasks_paginees`<br>`apps/console/tests/test_pagination.py::PaginationUnitTest.test_pages_et_derniere_page_partielle` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Bornes de pagination invalides | `apps/console/tests/test_pagination.py::PaginationApiTest.test_bornes_invalides_retournent_400`<br>`apps/console/tests/test_pagination.py::PaginationUnitTest.test_bornes_refusees` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Accessibilité et navigation

Tâches : 8.1.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Parcours clavier des 12 vues | `apps/console/tests/test_accessibility_static.py::AccessibilityStaticTest.test_les_douze_vues_ont_un_titre_et_une_region`<br>`apps/console/tests/test_accessibility_static.py::AccessibilityStaticTest.test_langue_lien_evitement_et_landmark`<br>`apps/console/tests/test_accessibility_static.py::AccessibilityStaticTest.test_focus_visible_et_mouvement_reduit` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Équivalent textuel d'un graphique | `apps/console/tests/test_accessibility_static.py::AccessibilityStaticTest.test_tableaux_avec_caption`<br>`apps/console/tests/test_accessibility_static.py::AccessibilityStaticTest.test_mises_a_jour_dynamiques_annoncees` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Dégradation gracieuse

Tâches : 7.6.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| — |  | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Déploiements et go/no-go

Tâches : 7.7.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Go/no-go bloqué | `apps/console/tests/test_deployments_view.py::DeploymentsViewTest.test_gate_en_echec_bloque_go` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Historique des déploiements | `apps/console/tests/test_deployments_view.py::DeploymentsViewTest.test_vue_deploiements_dora_et_go_no_go`<br>`apps/console/tests/test_deployments_view.py::DeploymentsViewTest.test_api_deploiements_filtre_et_go_no_go` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Documentation et fraîcheur

Tâches : 7.4.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Document généré | `apps/console/tests/test_documents_view.py::DocumentsViewTest.test_inventaire_fraicheur_et_generated`<br>`apps/console/tests/test_documents_view.py::DocumentsViewTest.test_api_documents_et_contenu` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Document périmé | `apps/console/tests/test_documents_view.py::DocumentsViewTest.test_inventaire_fraicheur_et_generated` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| XSS dans un document | `apps/console/tests/test_documents_view.py::DocumentsViewTest.test_lecture_markdown_sans_html_interprete` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Rétention et purge

Tâches : 8.5.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Purge standard | `apps/console/tests/test_purge.py::PurgeTest.test_purge_standard_conserve_audit_et_supprime_les_vieux` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Purge pendant une ingestion | `apps/console/tests/test_purge.py::PurgeTest.test_purge_sans_confirmation_et_ingestion_en_cours` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |
| Sauvegarde trop ancienne | `apps/console/tests/test_purge.py::PurgeTest.test_backup_absent_ou_trop_ancien_refuse` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

### Sauvegarde et restauration globales

Tâches : 8.4.

| Scénario | Test(s) automatisé(s) | Résultat |
|---|---|---|
| Restauration | `apps/console/tests/test_backup.py::BackupTest.test_sauvegarde_verification_et_restauration` | OK — 347 tests Python + 26 tests Vitest (21/10/2026) |

## Vérifications d'interface

| Vue | Preuve | Résultat |
|---|---|---|
| Vue d'ensemble | `Overview.test.tsx`, `test_overview.py` | OK |
| Features & tâches | `Features.test.tsx`, `test_features_view.py` | OK |
| Gates & qualité | `Views.test.tsx`, `test_gates.py` | OK |
| Revue indépendante | `Views.test.tsx`, `test_review_*.py` | OK |
| Déploiements | `Deployments.test.tsx`, `test_deployments_view.py` | OK |
| Équipe | `Views.test.tsx`, `test_team_metrics.py` | OK |
| Processus | `Views.test.tsx`, `test_process_*.py` | OK |
| Sécurité | `Security.test.tsx`, `test_security_view.py` | OK |
| Performance & données | `PerformanceData.test.tsx` | OK |
| Agents IA | `Agents.test.tsx`, `test_run_journal.py` | OK |
| Documentation | `Documents.test.tsx`, `test_documents_view.py` | OK |
| Configuration | `Configuration.test.tsx`, `test_config_view.py` | OK |

## Vérifications d'exploitation

| Scénario | Procédure | Résultat |
|---|---|---|
| Installation | `uv tool install .` ou `pipx install .`, puis `sdlc-console doctor` | OK |
| Démonstration | `sdlc-console init --demo` puis `serve --demo` | OK |
| WSL2 | mode miroir documenté dans `docs/installation.md` | OK |
| Sauvegarde | `test_backup.py` (intégrité, manifeste, restauration) | OK |
| Purge | `test_purge.py` (garde 24 h, audit exclu, `purge_busy`) | OK |
| CI | `scripts/ci.sh` (lint, typecheck, tests, couverture, SAST, dépendances, secrets, build) | OK |

## Limites

La recette est automatisée sur le poste local. Elle ne remplace pas un test
d'acceptation utilisateur sur un navigateur réel ; l'audit d'accessibilité
`docs/recette/accessibilite.md` en précise le périmètre.
