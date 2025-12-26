# Core Structure Analysis Report

**Generated:** 2025-12-13 16:44:51  
**Analyzed Path:** `resync/core`

---

## 📊 Overall Statistics

| Metric | Value |
|--------|-------|
| **Total Files** | 275 |
| **Total Lines** | 97,892 |
| **Average Lines/File** | 355 |
| **Existing Subdirectories** | 31 |

---

## 📁 Existing Directory Structure


### `root/` (119 files)

- `active_learning.py`
- `adaptive_eviction.py`
- `advanced_cache.py`
- `agent_manager.py`
- `agent_router.py`
- `alerting.py`
- `anomaly_detector.py`
- `app_context.py`
- `async_cache.py`
- `audit_db.py`
- ... and 109 more

### `health/` (18 files)

- `circuit_breaker_manager.py`
- `component_cache_manager.py`
- `enhanced_health_config_manager.py`
- `health_alerting.py`
- `health_check_retry.py`
- `health_check_service.py`
- `health_check_utils.py`
- `health_config_manager.py`
- `health_history_manager.py`
- `health_monitoring_coordinator.py`
- ... and 8 more

### `cache/` (13 files)

- `async_cache_refactored.py`
- `base_cache.py`
- `cache_factory.py`
- `cache_warmer.py`
- `embedding_model.py`
- `llm_cache_wrapper.py`
- `memory_manager.py`
- `persistence_manager.py`
- `redis_config.py`
- `reranker.py`
- ... and 3 more

### `utils/` (12 files)

- `common_error_handlers.py`
- `data_structures.py`
- `error_factories.py`
- `error_utils.py`
- `exception_utils.py`
- `executors.py`
- `json_commands.py`
- `json_parser.py`
- `llm.py`
- `llm_factories.py`
- ... and 2 more

### `health/health_checkers/` (11 files)

- `base_health_checker.py`
- `cache_health_checker.py`
- `connection_pools_health_checker.py`
- `cpu_health_checker.py`
- `database_health_checker.py`
- `filesystem_health_checker.py`
- `health_checker_factory.py`
- `memory_health_checker.py`
- `redis_health_checker.py`
- `tws_monitor_health_checker.py`
- ... and 1 more

### `knowledge_graph/` (8 files)

- `cache_manager.py`
- `extractor.py`
- `graph.py`
- `hybrid_rag.py`
- `models.py`
- `sync_manager.py`
- `tws_graph_expander.py`
- `tws_relations.py`

### `continual_learning/` (7 files)

- `active_learning.py`
- `audit_to_kg_pipeline.py`
- `context_enrichment.py`
- `feedback_retriever.py`
- `feedback_store.py`
- `orchestrator.py`
- `threshold_tuning.py`

### `idempotency/` (7 files)

- `config.py`
- `exceptions.py`
- `manager.py`
- `metrics.py`
- `models.py`
- `storage.py`
- `validation.py`

### `exceptions_pkg/` (7 files)

- `auth.py`
- `base.py`
- `integration.py`
- `network.py`
- `resource.py`
- `storage.py`
- `validation.py`

### `health/monitors/` (7 files)

- `cache_monitor.py`
- `connection_monitor.py`
- `database_monitor.py`
- `filesystem_monitor.py`
- `redis_monitor.py`
- `service_monitor.py`
- `system_monitor.py`

### `incident_response_pkg/` (6 files)

- `config.py`
- `detector.py`
- `models.py`
- `notifications.py`
- `playbook.py`
- `responder.py`

### `pools/` (5 files)

- `base_pool.py`
- `db_pool.py`
- `http_pool.py`
- `pool_manager.py`
- `redis_pool.py`

### `database/` (5 files)

- `config.py`
- `engine.py`
- `migrations.py`
- `models_registry.py`
- `schema.py`

### `specialists/` (5 files)

- `agents.py`
- `models.py`
- `parallel_executor.py`
- `sub_agent.py`
- `tools.py`

### `langgraph/` (5 files)

- `agent_graph.py`
- `checkpointer.py`
- `diagnostic_graph.py`
- `nodes.py`
- `parallel_graph.py`

### `security_dashboard_pkg/` (4 files)

- `compliance.py`
- `dashboard.py`
- `metrics.py`
- `threats.py`

### `multi_tenant/` (4 files)

- `multi_tenant_cache.py`
- `multi_tenant_kg.py`
- `tenant_manager.py`
- `tenant_middleware.py`

### `tws_multi/` (4 files)

- `instance.py`
- `learning.py`
- `manager.py`
- `session.py`

### `cache/mixins/` (4 files)

- `health_mixin.py`
- `metrics_mixin.py`
- `snapshot_mixin.py`
- `transaction_mixin.py`

### `database/repositories/` (4 files)

- `admin_users.py`
- `base.py`
- `stores.py`
- `tws_repository.py`

### `metrics/` (3 files)

- `continual_learning_metrics.py`
- `lightweight_store.py`
- `runtime_metrics.py`

### `graph_age/` (3 files)

- `age_service.py`
- `models.py`
- `queries.py`

### `compliance/` (3 files)

- `report_generator.py`
- `report_strategies.py`
- `types.py`

### `health_service_pkg/` (2 files)

- `config.py`
- `service.py`

### `vector/` (2 files)

- `embedding_provider.py`
- `pgvector_service.py`

### `langfuse/` (2 files)

- `observability.py`
- `prompt_manager.py`

### `monitoring/` (1 files)

- `evidently_monitor.py`

### `memory/` (1 files)

- `conversation_memory.py`

### `backup/` (1 files)

- `backup_service.py`

### `observability/` (1 files)

- `config.py`

### `database/models/` (1 files)

- `stores.py`

---

## 🎯 Suggested Thematic Grouping


### PLATFORM (85 files)

| File | Lines | Classes |
|------|-------|--------|
| async_cache.py | 1849 | CacheEntry, AsyncTTLCache |
| exceptions.py | 1412 | ErrorCode, ErrorSeverity, BaseAppException... |
| incident_response.py | 1096 | IncidentSeverity, IncidentStatus, IncidentCategory... |
| log_aggregator.py | 958 | LogLevel, LogSource, LogEntry... |
| backup_service.py | 916 | BackupType, BackupStatus, BackupInfo... |
| siem_integrator.py | 884 | SIEMType, EventFormat, SIEMStatus... |
| parallel_graph.py | 837 | DataSourceResult, ParallelState, ParallelConfig... |
| encrypted_audit.py | 833 | AuditEntry, EncryptionKey, AuditLogBlock... |
| service_discovery.py | 818 | DiscoveryBackend, ServiceStatus, LoadBalancingStrategy... |
| file_ingestor.py | 815 | FileIngestor |
| structured_logger.py | 809 | LoggerAdapter, PerformanceLogger, SafeEncodingFormatter... |
| agent_graph.py | 718 | Intent, AgentState, AgentGraphConfig... |
| advanced_cache.py | 717 | CacheEntry, CacheStats, InvalidationRule... |
| distributed_tracing.py | 684 | IntelligentSampler, TraceConfiguration, DistributedTracingManager... |
| prompt_manager.py | 669 | PromptType, PromptConfig, PromptTemplate... |

*... and 70 more files*

### OBSERVABILITY (82 files)

| File | Lines | Classes |
|------|-------|--------|
| security_dashboard.py | 1098 | MetricType, MetricCategory, SecurityMetric... |
| chaos_engineering.py | 1064 | ChaosTestResult, FuzzingScenario, ChaosEngineer... |
| soc2_compliance_refactored.py | 940 | ControlCategory, ControlStatus, SOC2Control... |
| evidently_monitor.py | 937 | DriftType, MonitoringSchedule, AlertSeverity... |
| tws_background_poller.py | 829 | EventType, AlertSeverity, TWSEvent... |
| anomaly_detector.py | 749 | AnomalyMetrics, AnomalyScore, MLModelConfig... |
| metrics.py | 687 | MetricCounter, MetricGauge, MetricHistogram... |
| metrics_collector.py | 642 | MetricType, MetricCategory, MetricDefinition... |
| strategies.py | 593 | CacheSetStrategy, StandardCacheSetStrategy, CacheRollbackStrategy... |
| stores.py | 593 | ConversationRepository, ContextContentRepository, ContextStore... |
| database_privilege_manager.py | 581 | UserRole, DatabasePermission, RolePermissions... |
| tws_monitor.py | 524 | PerformanceMetrics, Alert, TWSMonitor... |
| event_bus.py | 514 | SubscriptionType, Subscriber, WebSocketClient... |
| observability.py | 513 | LLMCallTrace, TraceSession, LangFuseTracer |
| filesystem_monitor.py | 511 | DiskSpaceStatus, IntegrityStatus, PermissionStatus... |

*... and 67 more files*

### RETRIEVAL (52 files)

| File | Lines | Classes |
|------|-------|--------|
| tools.py | 1842 | ToolPermission, UserRole, ToolRunStatus... |
| graph.py | 986 | ReadWriteLock, TWSKnowledgeGraph |
| hybrid_rag.py | 892 | QueryIntent, QueryClassification, QueryClassifier... |
| diagnostic_graph.py | 862 | DiagnosticPhase, ConfidenceLevel, DiagnosticState... |
| tws_graph_expander.py | 840 | GraphExpansionConfig, ExpansionStats, TWSGraphExpander |
| semantic_cache.py | 832 | CacheEntry, CacheResult, SemanticCache |
| multi_tenant_kg.py | 759 | MultiTenantKGConfig, MultiTenantKGService |
| age_service.py | 749 | AGEGraphService, FallbackGraphService |
| continual_learning_engine.py | 695 | ProcessingResult, FeedbackResult, ContinualLearningEngine |
| tenant_manager.py | 686 | TenantEnvironment, TenantStatus, TenantLimits... |
| audit_to_kg_pipeline.py | 641 | ErrorType, AuditFinding, ErrorTriplet... |
| pgvector_service.py | 591 | DistanceMetric, VectorDocument, SearchResult... |
| checkpointer.py | 572 | CheckpointRecord, PostgresCheckpointer |
| query_cache.py | 571 | QueryFingerprint, QueryExecutionStats, QueryResult... |
| tws_relations.py | 538 | TWSRelationType, TWSNodeType, TWSNode... |

*... and 37 more files*

### AGENTS (27 files)

| File | Lines | Classes |
|------|-------|--------|
| agent_router.py | 1111 | RoutingMode, Intent, IntentClassification... |
| agents.py | 861 | QueryClassifier, BaseSpecialist, JobAnalystAgent... |
| agent_manager.py | 693 | AgentsConfig, AgentManager, UnifiedAgent... |
| nodes.py | 624 | BaseNode, RouterConfig, RouterNode... |
| extractor.py | 543 | Triplet, TripletExtractor |
| embedding_router.py | 522 | RouterIntent, ClassificationResult, EmbeddingRouter |
| sub_agent.py | 518 | SubAgentConfig, SubAgentStatus, SubAgentResult... |
| intent_examples_expanded.py | 489 |  |
| parallel_executor.py | 407 | ToolRequest, ToolResponse, ExecutionStrategy... |
| llm_optimizer.py | 336 | TWS_LLMOptimizer |
| admin_users.py | 334 | AdminUserRepository |
| embedding_provider.py | 292 | EmbeddingConfig, EmbeddingProvider, LiteLLMEmbeddingProvider... |
| litellm_init.py | 260 | LiteLLMMetrics, LiteLLMManager, RouterLike |
| llm_monitor.py | 246 | LLMCost, LLMUsageStats, LLMCostMonitor... |
| models.py | 211 | SpecialistType, TeamExecutionMode, SpecialistConfig... |

*... and 12 more files*

### SECURITY (18 files)

| File | Lines | Classes |
|------|-------|--------|
| gdpr_compliance.py | 912 | DataCategory, RetentionPolicy, ConsentStatus... |
| report_strategies.py | 655 | ComplianceCalculationError, StrategyValidationError, ComplianceManagerProtocol... |
| database_security.py | 512 | DatabaseSecurityError, DatabaseInputValidator, DatabaseAuditor... |
| security.py | 395 | InputSanitizer |
| report_generator.py | 385 | ComplianceReportGenerator |
| security_hardening.py | 250 | SecurityHardeningConfig |
| exception_utils.py | 229 | SuppressedExceptionTracker |
| threats.py | 152 | ThreatSeverity, ThreatType, Threat... |
| compliance.py | 137 | ComplianceFramework, ComplianceStatus, ComplianceCheck... |
| csp_template_response.py | 99 | CSPTemplateResponse |
| dashboard.py | 97 | SecurityDashboard |
| metrics.py | 85 | SecurityMetrics |
| header_parser.py | 80 | CSPParser, SecurityHeaderParser |
| types.py | 59 | SOC2TrustServiceCriteria, SOC2ComplianceManagerProtocol, SOC2ComplianceManager |
| csp_jinja_extension.py | 57 | CSPNonceExtension |

*... and 3 more files*

### TWS (9 files)

| File | Lines | Classes |
|------|-------|--------|
| tws_rag_queries.py | 748 | QueryIntent, QueryResult, TWSQueryProcessor |
| sync_manager.py | 565 | ChangeType, SyncChange, SyncStats... |
| tws_repository.py | 495 | JobStatus, PatternMatch, TWSSnapshotRepository... |
| session.py | 204 | TWSSession, SessionManager |
| tws_status_store.py | 195 | TWSStatusStore |
| instance.py | 185 | TWSInstanceStatus, TWSEnvironment, TWSInstanceConfig... |
| learning.py | 73 | TWSLearningStore |
| executors.py | 63 | OptimizedExecutors |
| dependencies.py | 49 |  |

### UNKNOWN (2 files)

| File | Lines | Classes |
|------|-------|--------|
| global_utils.py | 98 |  |
| active_learning.py | 12 |  |

---

## 🔍 Potential Duplications

Files with similar names that may need consolidation:


### `config` (5 files, 784 total lines)

- `resync/core/health_service_pkg/config.py` (47 lines)
- `resync/core/incident_response_pkg/config.py` (46 lines)
- `resync/core/database/config.py` (163 lines)
- `resync/core/idempotency/config.py` (20 lines)
- `resync/core/observability/config.py` (508 lines)

### `models` (5 files, 966 total lines)

- `resync/core/knowledge_graph/models.py` (364 lines)
- `resync/core/graph_age/models.py` (220 lines)
- `resync/core/incident_response_pkg/models.py` (98 lines)
- `resync/core/idempotency/models.py` (73 lines)
- `resync/core/specialists/models.py` (211 lines)

### `exceptions` (3 files, 1852 total lines)

- `resync/core/exceptions.py` (1412 lines)
- `resync/core/exceptions_enhanced.py` (421 lines)
- `resync/core/idempotency/exceptions.py` (19 lines)

### `metrics` (3 files, 796 total lines)

- `resync/core/metrics.py` (687 lines)
- `resync/core/security_dashboard_pkg/metrics.py` (85 lines)
- `resync/core/idempotency/metrics.py` (24 lines)

### `active_learning` (2 files, 94 total lines)

- `resync/core/active_learning.py` (12 lines)
- `resync/core/continual_learning/active_learning.py` (82 lines)

### `audit_to_kg_pipeline` (2 files, 1169 total lines)

- `resync/core/audit_to_kg_pipeline.py` (641 lines)
- `resync/core/continual_learning/audit_to_kg_pipeline.py` (528 lines)

### `context_enrichment` (2 files, 960 total lines)

- `resync/core/context_enrichment.py` (494 lines)
- `resync/core/continual_learning/context_enrichment.py` (466 lines)

### `async_cache` (2 files, 2116 total lines)

- `resync/core/async_cache.py` (1849 lines)
- `resync/core/cache/async_cache_refactored.py` (267 lines)

### `manager` (2 files, 861 total lines)

- `resync/core/tws_multi/manager.py` (390 lines)
- `resync/core/idempotency/manager.py` (471 lines)

### `validation` (2 files, 96 total lines)

- `resync/core/idempotency/validation.py` (39 lines)
- `resync/core/exceptions_pkg/validation.py` (57 lines)

### `storage` (2 files, 147 total lines)

- `resync/core/idempotency/storage.py` (59 lines)
- `resync/core/exceptions_pkg/storage.py` (88 lines)

### `base` (2 files, 534 total lines)

- `resync/core/exceptions_pkg/base.py` (106 lines)
- `resync/core/database/repositories/base.py` (428 lines)

### `stores` (2 files, 1117 total lines)

- `resync/core/database/models/stores.py` (524 lines)
- `resync/core/database/repositories/stores.py` (593 lines)

---

## 📏 Largest Files (Top 25)

| File | Lines | Classes | Functions |
|------|-------|---------|----------|
| async_cache.py | 1849 | 2 | 24 |
| tools.py | 1842 | 28 | 63 |
| exceptions.py | 1412 | 48 | 46 |
| agent_router.py | 1111 | 12 | 11 |
| security_dashboard.py | 1098 | 12 | 32 |
| incident_response.py | 1096 | 12 | 20 |
| chaos_engineering.py | 1064 | 4 | 9 |
| graph.py | 986 | 2 | 13 |
| log_aggregator.py | 958 | 8 | 16 |
| soc2_compliance_refactored.py | 940 | 9 | 16 |
| evidently_monitor.py | 937 | 10 | 21 |
| backup_service.py | 916 | 5 | 18 |
| gdpr_compliance.py | 912 | 11 | 20 |
| hybrid_rag.py | 892 | 4 | 14 |
| siem_integrator.py | 884 | 12 | 24 |
| diagnostic_graph.py | 862 | 8 | 11 |
| agents.py | 861 | 10 | 25 |
| tws_graph_expander.py | 840 | 3 | 15 |
| parallel_graph.py | 837 | 4 | 1 |
| encrypted_audit.py | 833 | 6 | 19 |
| semantic_cache.py | 832 | 3 | 6 |
| tws_background_poller.py | 829 | 7 | 22 |
| service_discovery.py | 818 | 9 | 11 |
| file_ingestor.py | 815 | 1 | 14 |
| structured_logger.py | 809 | 4 | 30 |

---

## 💡 Recommendations

1. **119 files in root directory** - Consider moving to thematic subdirectories
2. **13 potential duplications** - Review and consolidate
3. **72 files > 500 lines** - Consider splitting

---

## 🚀 Migration Priority


Based on the analysis, recommended migration order:

1. **Platform** (config, DI, exceptions) - Foundation for other modules
2. **Observability** (health, metrics, logging) - Needed for monitoring migration
3. **Security** (auth, validation) - Independent module
4. **Retrieval** (cache, RAG, KG) - Large but cohesive
5. **Agents** (LLM, specialists) - Depends on retrieval
6. **TWS** (client, monitor) - Domain-specific, last

