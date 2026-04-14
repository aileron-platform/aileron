#!/usr/bin/env python3
"""
Mock Responses for testing
提供測試用的模擬回應資料
"""

from typing import Dict, Any, List
from datetime import datetime


class MockResponses:
    """模擬回應資料生成器"""

    @staticmethod
    def health_check_response() -> Dict[str, Any]:
        """健康檢查成功回應"""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "workspace-manager",
            "version": "1.0.0",
            "database": "connected",
            "uptime": "0d 0h 1m 23s"
        }

    @staticmethod
    def health_check_degraded_response() -> Dict[str, Any]:
        """健康檢查降級回應"""
        return {
            "status": "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "workspace-manager",
            "version": "1.0.0",
            "database": "slow",
            "uptime": "0d 0h 1m 23s",
            "warnings": ["Database response time elevated"]
        }

    @staticmethod
    def automation_job_response() -> Dict[str, Any]:
        """自動化任務回應"""
        return {
            "id": "test-job-001",
            "name": "Test Automation Job",
            "status": "running",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "schedule": "0 9 * * 1-5",
            "config": {
                "action": "backup",
                "target": "/workspace",
                "retention_days": 30
            },
            "last_run": datetime.utcnow().isoformat(),
            "next_run": datetime.utcnow().isoformat(),
            "execution_count": 5,
            "success_count": 4,
            "failure_count": 1
        }

    @staticmethod
    def automation_jobs_list_response() -> List[Dict[str, Any]]:
        """自動化任務列表回應"""
        return [
            {
                "id": "test-job-001",
                "name": "Backup Database",
                "status": "active",
                "schedule": "0 2 * * *",
                "created_at": datetime.utcnow().isoformat(),
                "last_run": datetime.utcnow().isoformat(),
                "next_run": datetime.utcnow().isoformat()
            },
            {
                "id": "test-job-002",
                "name": "Cleanup Logs",
                "status": "active",
                "schedule": "0 3 * * 0",
                "created_at": datetime.utcnow().isoformat(),
                "last_run": datetime.utcnow().isoformat(),
                "next_run": datetime.utcnow().isoformat()
            }
        ]

    @staticmethod
    def settings_response() -> Dict[str, Any]:
        """設定回應"""
        return {
            "id": "settings-001",
            "workspace_id": "workspace-001",
            "key": "test_setting",
            "value": "test_value",
            "type": "string",
            "description": "Test setting for integration tests",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "created_by": "test-user",
            "updated_by": "test-user"
        }

    @staticmethod
    def settings_list_response() -> List[Dict[str, Any]]:
        """設定列表回應"""
        return [
            {
                "id": "settings-001",
                "key": "backup_enabled",
                "value": True,
                "type": "boolean",
                "description": "Enable automatic backups"
            },
            {
                "id": "settings-002",
                "key": "max_workspace_size",
                "value": 1024,
                "type": "integer",
                "description": "Maximum workspace size in MB"
            }
        ]

    @staticmethod
    def error_response(message: str = "Internal server error") -> Dict[str, Any]:
        """錯誤回應"""
        return {
            "error": True,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": 500
        }

    @staticmethod
    def not_found_response(resource: str = "Resource") -> Dict[str, Any]:
        """404 回應"""
        return {
            "error": True,
            "message": f"{resource} not found",
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": 404
        }

    @staticmethod
    def validation_error_response(errors: List[str]) -> Dict[str, Any]:
        """驗證錯誤回應"""
        return {
            "error": True,
            "message": "Validation failed",
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": 422
        }

    @staticmethod
    def success_response(message: str = "Operation successful") -> Dict[str, Any]:
        """成功回應"""
        return {
            "success": True,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }