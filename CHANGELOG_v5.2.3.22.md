# Resync v5.2.3.22 - System Configuration Web Interface

## Summary

Added comprehensive system configuration management via web interface with neumorphic soft UI design.

## Categories & Fields (Total: 56 configurable fields)

### 1. Performance & Cache (8 fields)
- robust_cache_max_items (100-1,000,000)
- robust_cache_max_memory_mb (10-4096 MB)
- robust_cache_eviction_batch_size (1-1000)
- robust_cache_enable_weak_refs (on/off)
- db_pool_min_size (1-100) [restart]
- db_pool_max_size (1-1000) [restart]
- redis_pool_min_size (1-100) [restart]
- redis_pool_max_size (1-1000) [restart]

### 2. TWS Monitoring (11 fields)
- tws_polling_enabled (on/off)
- tws_polling_interval_seconds (5-300)
- tws_polling_mode (fixed/adaptive/scheduled)
- tws_job_stuck_threshold_minutes (10-1440)
- tws_job_late_threshold_minutes (5-720)
- tws_anomaly_failure_rate_threshold (0.01-1.0)
- tws_pattern_detection_enabled (on/off)
- tws_pattern_detection_interval_minutes (15-1440)
- tws_pattern_min_confidence (0.1-1.0)
- tws_solution_correlation_enabled (on/off)
- tws_solution_min_success_rate (0.0-1.0)

### 3. Data Retention (3 fields)
- tws_retention_days_full (1-30 days)
- tws_retention_days_summary (7-90 days)
- tws_retention_days_patterns (30-365 days)

### 4. Rate Limiting (5 fields)
- rate_limit_public_per_minute (1-10000)
- rate_limit_authenticated_per_minute (1-100000)
- rate_limit_critical_per_minute (1-1000)
- rate_limit_websocket_per_minute (1-1000)
- rate_limit_sliding_window (on/off)

### 5. RAG Service (4 fields)
- rag_service_url (string)
- rag_service_timeout (10-600 seconds)
- rag_service_max_retries (0-10)
- rag_service_retry_backoff (0.1-10.0)

### 6. AI Models (4 fields)
- llm_endpoint (string)
- llm_timeout (10-300 seconds)
- auditor_model_name (select: gpt-3.5/4/claude)
- agent_model_name (select: gpt-3.5/4/claude)

### 7. Logging (3 fields)
- log_level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- log_format (text/json) [restart]
- log_sensitive_data_redaction (on/off)

### 8. Notifications (4 fields)
- tws_browser_notifications_enabled (on/off)
- tws_teams_notifications_enabled (on/off)
- tws_dashboard_refresh_seconds (1-60)
- tws_dashboard_theme (auto/light/dark)

### 9. Feature Flags (4 fields)
- MIGRATION_USE_NEW_CACHE (on/off) [restart]
- MIGRATION_USE_NEW_TWS (on/off) [restart]
- MIGRATION_USE_NEW_RATE_LIMIT (on/off) [restart]
- MIGRATION_ENABLE_METRICS (on/off)

## API Endpoints

```
GET  /api/v1/system-config/categories     # Get all config categories
GET  /api/v1/system-config/category/{name} # Get specific category
POST /api/v1/system-config/update         # Update config values
GET  /api/v1/system-config/resources      # Get system resources
POST /api/v1/system-config/gc             # Trigger garbage collection
POST /api/v1/system-config/cache/clear    # Clear all caches
```

## UI Features

- Real-time resource monitor (CPU, Memory, Disk)
- Tab-based category navigation
- Type-appropriate controls (toggle, input, select, range)
- Change tracking with unsaved indicator
- Restart required warnings
- Discard/Save functionality
- Neumorphic soft UI design

## Files Created/Modified

- resync/api/system_config.py (API endpoints + models)
- templates/partials/system_config_section.html (UI template)
- static/css/admin-neumorphic.css (extended styles)

## Integration

Add to admin.html sidebar:
```html
<a class="nav-link" href="#" data-target="system-settings">
    <i class="fas fa-cogs me-2"></i>System Configuration
</a>
```

Add router to main.py:
```python
from resync.api.system_config import router as system_config_router
app.include_router(system_config_router)
```

