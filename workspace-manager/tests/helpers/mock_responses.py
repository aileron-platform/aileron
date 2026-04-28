#!/usr/bin/env python3
"""
Mock Responses for testing
Provides mock response data for testing
"""

from typing import Dict, Any, List
from datetime import datetime


class MockResponses:
    """Mock response data generator"""

    @staticmethod
    def health_check_response() -> Dict[str, Any]:
        """Health check success response"""
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
        """Health check degraded response"""
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
        """Automation job response"""
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
        """Automation jobs list response"""
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
        """Settings response"""
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
        """Settings list response"""
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
        """Error response"""
        return {
            "error": True,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": 500
        }

    @staticmethod
    def not_found_response(resource: str = "Resource") -> Dict[str, Any]:
        """404 response"""
        return {
            "error": True,
            "message": f"{resource} not found",
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": 404
        }

    @staticmethod
    def validation_error_response(errors: List[str]) -> Dict[str, Any]:
        """Validation error response"""
        return {
            "error": True,
            "message": "Validation failed",
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": 422
        }

    @staticmethod
    def success_response(message: str = "Operation successful") -> Dict[str, Any]:
        """Success response"""
        return {
            "success": True,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }