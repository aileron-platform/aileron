"""Celery 應用配置"""

from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

from app.config.settings import get_settings

# 載入設定
settings = get_settings()

# 從環境變數讀取時區，預設為 Asia/Taipei
# 這樣可以配合 Docker 容器的 TZ 環境變數
CELERY_TIMEZONE = os.getenv("TZ", "Asia/Taipei")

# 建立 Celery 應用
celery_app = Celery(
    "workspace-manager",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"]  # 引入任務模組
)

# Celery 配置
# 使用系統時區而非固定 UTC，讓排程任務能正確處理本地時間
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=CELERY_TIMEZONE,  # 使用系統時區
    enable_utc=False,  # 不強制使用 UTC，使用本地時區
    task_track_started=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,  # 結果保留 1 小時
    # 禁用 Celery events 以解決 Flower 2.0.1 + Celery 5.5.3 的 pidbox 兼容性問題
    # Ref: https://github.com/celery/celery/issues/7561
    worker_send_task_events=False,
    worker_disable_rate_limits=True,
)

celery_app.conf.beat_schedule = {
    "automation-dispatch-due-jobs": {
        "task": "automation.dispatch_due_jobs",
        "schedule": 60.0,  # 每分鐘執行一次
    },
    "automation-cleanup-stuck-executions": {
        "task": "automation.cleanup_stuck_executions",
        "schedule": 300.0,  # 每 5 分鐘執行一次
        "kwargs": {"timeout_minutes": 60},  # 清理超過 60 分鐘的卡住任務
    },
    "automation-cleanup-expired-queue": {
        "task": "automation.cleanup_expired_queue",
        "schedule": 300.0,  # 每 5 分鐘執行一次
    },
    "knowledge-bases-reconcile-kb-quota": {
        "task": "knowledge_bases.reconcile_kb_quota",
        "schedule": crontab(hour=2, minute=0),  # 每日凌晨 2 點校正 KB 用量
    },
    "knowledge-bases-cleanup-tombstoned-kb": {
        "task": "knowledge_bases.cleanup_tombstoned_kb",
        "schedule": crontab(hour=3, minute=0),  # 每日凌晨 3 點清理 tombstoned KB
    },
}

# 導出為 app，這樣 celery -A app.celery.app 就能找到
app = celery_app
