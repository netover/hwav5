"""
Unified Configuration API

REST API for managing ALL Resync configurations with hot reload.

Endpoints:
- GET /api/admin/config/all - Get all configs
- GET /api/admin/config/{name} - Get specific config
- POST /api/admin/config/{name}/update - Update config (hot reload)
- GET /api/admin/config/status - Get config system status
- POST /api/admin/config/reload - Force reload all configs

Author: Resync Team
Version: 5.9.8
"""

from datetime import datetime
from typing import Any, Dict

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from resync.core.unified_config import get_config_manager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/config", tags=["configuration"])


class ConfigUpdateRequest(BaseModel):
    """Request to update configuration."""
    section: str
    data: Dict[str, Any]
    create_backup: bool = True


class ConfigReloadResponse(BaseModel):
    """Response for config reload."""
    status: str
    configs_loaded: list[str]
    errors: list[str] = []


@router.get("/all")
async def get_all_configs():
    """
    Get all configuration files.
    
    Returns complete configuration tree for entire system.
    
    Example response:
    {
        "graphrag": {...},
        "ai": {...},
        "monitoring": {...},
        "system": {...}
    }
    """
    try:
        manager = get_config_manager()
        configs = manager.get_all_configs()
        
        return {
            "status": "success",
            "configs": configs,
            "hot_reload_active": manager.observer is not None
        }
        
    except Exception as e:
        logger.error(f"Failed to get configs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_name}")
async def get_config(config_name: str, section: str = None):
    """
    Get specific configuration.
    
    Args:
        config_name: Name of config (graphrag, ai, monitoring, system)
        section: Optional section within config
        
    Example:
        GET /api/admin/config/ai
        GET /api/admin/config/ai?section=specialists
    """
    try:
        manager = get_config_manager()
        
        if config_name not in manager.CONFIG_FILES:
            raise HTTPException(
                status_code=404,
                detail=f"Config not found: {config_name}"
            )
        
        config = manager.get_config(config_name, section)
        
        return {
            "status": "success",
            "config_name": config_name,
            "section": section,
            "data": config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config {config_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_name}/update")
async def update_config(config_name: str, request: ConfigUpdateRequest):
    """
    Update configuration with hot reload.
    
    Changes are:
    1. Applied immediately to runtime (hot)
    2. Saved to file (persists across restarts)
    3. Backed up automatically
    
    Example:
        POST /api/admin/config/ai/update
        {
            "section": "specialists",
            "data": {
                "max_parallel_specialists": 6,
                "timeout_seconds": 60
            }
        }
        
    Response:
        {
            "status": "success",
            "message": "Config updated with hot reload",
            "config_name": "ai",
            "section": "specialists",
            "updated_fields": ["max_parallel_specialists", "timeout_seconds"]
        }
    """
    try:
        manager = get_config_manager()
        
        if config_name not in manager.CONFIG_FILES:
            raise HTTPException(
                status_code=404,
                detail=f"Config not found: {config_name}"
            )
        
        # Update config (saves + hot reloads)
        await manager.update_config(
            config_name=config_name,
            section=request.section,
            data=request.data,
            create_backup=request.create_backup
        )
        
        return {
            "status": "success",
            "message": "Config updated with hot reload (persists across restarts)",
            "config_name": config_name,
            "section": request.section,
            "updated_fields": list(request.data.keys()),
            "hot_reload": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update config {config_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_config_status():
    """
    Get configuration system status.
    
    Returns:
    - Hot reload status
    - Loaded configs
    - Config file paths
    - Last reload times
    """
    try:
        manager = get_config_manager()
        
        configs_loaded = list(manager.configs.keys())
        config_files = {
            name: str(path)
            for name, path in manager.CONFIG_FILES.items()
        }
        
        return {
            "status": "operational",
            "hot_reload_active": manager.observer is not None,
            "configs_loaded": configs_loaded,
            "config_files": config_files,
            "total_configs": len(configs_loaded)
        }
        
    except Exception as e:
        logger.error(f"Failed to get config status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload")
async def reload_all_configs():
    """
    Force reload all configurations.
    
    Useful for:
    - Manual refresh after external changes
    - Troubleshooting
    - Initial load
    """
    try:
        manager = get_config_manager()
        
        configs_loaded = []
        errors = []
        
        for name, path in manager.CONFIG_FILES.items():
            try:
                if path.exists():
                    await manager.reload_config_file(path)
                    configs_loaded.append(name)
                else:
                    errors.append(f"Config file not found: {name}")
            except Exception as e:
                errors.append(f"Failed to reload {name}: {str(e)}")
        
        status = "success" if not errors else "partial"
        
        return {
            "status": status,
            "configs_loaded": configs_loaded,
            "errors": errors,
            "total_loaded": len(configs_loaded)
        }
        
    except Exception as e:
        logger.error(f"Failed to reload configs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backups")
async def list_config_backups():
    """
    List all configuration backups.
    
    Returns list of backup files with timestamps.
    """
    try:
        from pathlib import Path
        
        backup_dir = Path(__file__).parent.parent.parent / "config" / "backups"
        
        if not backup_dir.exists():
            return {
                "status": "success",
                "backups": [],
                "total": 0
            }
        
        backups = []
        
        for backup_file in backup_dir.glob("*.toml.bak"):
            stat = backup_file.stat()
            
            backups.append({
                "filename": backup_file.name,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
                "path": str(backup_file)
            })
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x["modified"], reverse=True)
        
        return {
            "status": "success",
            "backups": backups,
            "total": len(backups),
            "backup_dir": str(backup_dir)
        }
        
    except Exception as e:
        logger.error(f"Failed to list backups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backups/{filename}/restore")
async def restore_config_backup(filename: str):
    """
    Restore configuration from backup.
    
    WARNING: This will overwrite current configuration!
    """
    try:
        from pathlib import Path
        import shutil
        
        backup_dir = Path(__file__).parent.parent.parent / "config" / "backups"
        backup_file = backup_dir / filename
        
        if not backup_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Backup not found: {filename}"
            )
        
        # Extract config name from filename
        # Format: graphrag_20241225_150300.toml.bak
        config_name = filename.split('_')[0]
        
        manager = get_config_manager()
        
        if config_name not in manager.CONFIG_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown config: {config_name}"
            )
        
        config_file = manager.CONFIG_FILES[config_name]
        
        # Create backup of current before restoring
        current_backup = backup_dir / f"{config_name}_before_restore_{int(datetime.now().timestamp())}.toml.bak"
        shutil.copy2(config_file, current_backup)
        
        # Restore from backup
        shutil.copy2(backup_file, config_file)
        
        # Trigger hot reload
        await manager.reload_config_file(config_file)
        
        return {
            "status": "success",
            "message": "Config restored from backup with hot reload",
            "config_name": config_name,
            "backup_file": filename,
            "current_backed_up_to": current_backup.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
