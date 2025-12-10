# CHANGELOG v5.2.3.27 - Threshold Auto-Tuning (Merged)

**Release Date:** December 10, 2024  
**Version:** 5.2.3.27

## Overview

This release merges the two existing auto-tuning implementations into a unified, English-language system with the best features from both versions.

## 🔀 Merged Features

### From Original Project (auto_tuning.py)
- ✅ `min_entity_count` threshold tracking
- ✅ Compact code structure
- ✅ Direct approve/reject workflow for recommendations

### From Delivered Project (threshold_tuning.py)
- ✅ Circuit breaker with automatic activation (30% F1 drop)
- ✅ Automatic rollback on performance degradation (20% F1 drop)
- ✅ Mode-specific adjustment parameters (MID vs HIGH)
- ✅ Daily metrics endpoint for charting
- ✅ Comprehensive test suite (644 lines)
- ✅ More granular API endpoints (14 endpoints)

## 🗂️ File Changes

### New Files
- `resync/core/continual_learning/threshold_tuning.py` (1,716 lines)
- `resync/fastapi_app/api/v1/routes/admin_threshold_tuning.py` (425 lines)

### Removed Files
- `resync/core/continual_learning/auto_tuning.py`
- `resync/fastapi_app/api/v1/routes/admin_auto_tuning.py`

### Modified Files
- `resync/core/continual_learning/__init__.py` - Updated exports
- `resync/fastapi_app/main.py` - Updated router imports
- `templates/admin.html` - English UI, new features

## 🎛️ Thresholds Managed

| Threshold | Default | Min | Max | Description |
|-----------|---------|-----|-----|-------------|
| `classification_confidence` | 0.6 | 0.4 | 0.8 | Intent classification confidence |
| `rag_similarity` | 0.7 | 0.5 | 0.9 | RAG retrieval similarity |
| `error_similarity` | 0.85 | 0.7 | 0.95 | Error pattern matching |
| `min_entity_count` | 1.0 | 0.0 | 5.0 | Minimum entities for confidence |

## 📡 API Endpoints

Base path: `/api/v1/admin/threshold-tuning`

### Status & Mode
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Get full system status |
| GET | `/mode` | Get current mode |
| PUT | `/mode` | Set mode (off/low/mid/high) |

### Thresholds
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/thresholds` | Get all thresholds |
| GET | `/thresholds/{name}` | Get specific threshold |
| PUT | `/thresholds/{name}` | Update threshold value |
| POST | `/reset` | Reset to defaults |
| POST | `/rollback` | Rollback to last good |

### Metrics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/metrics` | Get metrics summary |
| GET | `/metrics/daily` | Get daily metrics |

### Recommendations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/recommendations` | Get pending recommendations |
| POST | `/recommendations/generate` | Generate new recommendations |
| POST | `/recommendations/{id}/approve` | Approve recommendation |
| POST | `/recommendations/{id}/reject` | Reject recommendation |

### Auto-Adjustment
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auto-adjust` | Trigger adjustment cycle |
| GET | `/circuit-breaker/status` | Get circuit breaker status |
| POST | `/circuit-breaker/reset` | Reset circuit breaker |

### Audit
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/audit-log` | Get change history |

## ⚙️ Mode Parameters

### OFF
- No metrics collection
- No auto-adjustment
- Static thresholds

### LOW
- ✅ Metrics collection
- ✅ Recommendations generation
- ❌ Auto-adjustment
- Smoothing factor: 0.9

### MID (Conservative)
- ✅ Metrics collection
- ✅ Recommendations generation
- ✅ Auto-adjustment
- Max change: ±5% per cycle
- Interval: 24 hours
- Min data points: 50
- Smoothing factor: 0.7

### HIGH (Aggressive)
- ✅ Metrics collection
- ✅ Recommendations generation
- ✅ Auto-adjustment
- Max change: ±10% per cycle
- Interval: 12 hours
- Min data points: 30
- Smoothing factor: 0.5

## 🛡️ Safety Features

### Circuit Breaker
- **Activation:** F1 score drops >30% from baseline
- **Effect:** Disables auto-adjustment until manual reset
- **Cooldown:** 24 hours before can reset
- **UI Alert:** Red banner displayed in admin panel

### Automatic Rollback
- **Trigger:** F1 score drops >20% from baseline
- **Action:** Restores last known good thresholds
- **Audit:** Logged with full context

### Bounds Enforcement
- All threshold changes clamped to min/max bounds
- Prevents extreme values that could degrade system

## 🎨 UI Changes

### Menu
- Renamed: "Auto-Tuning" → "Threshold Tuning"
- Badge shows current mode with color coding

### Cards
1. **Auto-Tuning Level** - Slider (OFF/LOW/MID/HIGH) with descriptions
2. **Effectiveness Metrics** - Review rate, FP/FN rates, F1, Precision, Recall
3. **Current Thresholds** - Table with edit buttons
4. **Recommendations** - Cards with approve/reject buttons
5. **Change History** - Audit log with icons and filtering

### All Labels in English
- Mode descriptions
- Button labels
- Table headers
- Alert messages

## 📊 Database Schema

### Tables
- `tuning_config` - Key-value configuration
- `thresholds` - Current threshold values and bounds
- `daily_metrics` - Aggregated daily metrics
- `review_outcomes` - Individual review results
- `recommendations` - Pending/applied/rejected recommendations
- `audit_log` - Complete change history

## 🧪 Testing

Test file: `tests/core/test_threshold_tuning.py` (644 lines)

Coverage includes:
- Mode management (7 tests)
- Threshold management (7 tests)
- Metrics calculation (11 tests)
- Recommendations (4 tests)
- Auto-adjustment (3 tests)
- Circuit breaker (3 tests)
- Rollback (2 tests)
- Audit log (3 tests)
- Full status (2 tests)
- Dataclass tests (11 tests)
- Singleton tests (1 test)

## 📝 Migration Notes

If upgrading from a previous version:

1. The API endpoint base changed from `/api/v1/admin/auto-tuning` to `/api/v1/admin/threshold-tuning`
2. The database file changed from `auto_tuning.db` to `threshold_tuning.db`
3. Old database data will NOT be migrated automatically
4. Recommend starting fresh in OFF mode, then enabling LOW to collect metrics

## ✅ Validation

- All Python files compile successfully
- No syntax errors
- Routes properly registered in FastAPI app
- UI JavaScript functions implemented
- Test suite ready for execution
