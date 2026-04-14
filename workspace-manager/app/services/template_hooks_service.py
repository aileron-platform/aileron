"""模板 Hooks 配置服務"""

from __future__ import annotations

import json
import logging
from typing import Optional, List

from sqlalchemy.orm import Session

from app.models import HooksConfigResponse, HooksConfigUpdateRequest
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateHooksService(TemplateBaseService):
    """處理模板的 Hooks 配置管理"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_hooks_config(self, template_id: str) -> Optional[HooksConfigResponse]:
        """取得模板的 Hooks 配置"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None

        hooks_file = self._get_template_dir(template_id) / "hooks" / "hooks.json"
        if not hooks_file.exists():
            return HooksConfigResponse(template_id=template_id, hooks={})

        try:
            hooks_data = json.loads(hooks_file.read_text(encoding="utf-8"))
            return HooksConfigResponse(template_id=template_id, hooks=hooks_data.get("hooks", {}))
        except Exception as e:
            logger.error(f"讀取 Hooks 配置失敗: {e}")
            return HooksConfigResponse(template_id=template_id, hooks={})

    def update_hooks_config(
        self, template_id: str, payload: HooksConfigUpdateRequest
    ) -> Optional[HooksConfigResponse]:
        """更新模板的 Hooks 配置"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None

        # 確保 hooks 目錄存在
        hooks_dir = self._get_template_dir(template_id) / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        hooks_file = hooks_dir / "hooks.json"
        try:
            # 將 HookRule 對象轉換為可序列化的字典，排除None值
            hooks_dict = {
                event_name: [rule.model_dump(exclude_none=True) for rule in rules]
                for event_name, rules in payload.hooks.items()
            }
            hooks_data = {"hooks": hooks_dict}
            hooks_file.write_text(
                json.dumps(hooks_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.info(f"已更新模板 {template_id} 的 Hooks 配置")
            return HooksConfigResponse(template_id=template_id, hooks=payload.hooks)
        except Exception as e:
            logger.error(f"更新 Hooks 配置失敗: {e}")
            raise

    def load_hooks(self, template_id: str) -> List:
        """載入 Hooks 配置"""
        from app.models.template import TemplateHook

        hooks_file = self._get_template_dir(template_id) / "hooks" / "hooks.json"
        if not hooks_file.exists():
            return []

        try:
            hooks_data = json.loads(hooks_file.read_text(encoding="utf-8"))
            hooks = []

            for event_name, hook_rules in hooks_data.get("hooks", {}).items():
                for rule_index, rule in enumerate(hook_rules):
                    # 為每個 hook execution 創建一個 TemplateHook
                    for hook_index, hook_exec in enumerate(rule.get("hooks", [])):
                        hooks.append(TemplateHook(
                            id=f"{event_name}-{rule_index}-{hook_index}",
                            name=f"{event_name} Hook - Rule {rule_index + 1}",
                            event=event_name,
                            matcher=rule.get("matcher", "*"),
                            action=hook_exec.get("type", "command"),
                            command=hook_exec.get("command"),
                            timeout=hook_exec.get("timeout", 30),
                        ))

            return hooks
        except Exception as e:
            logger.error(f"載入 Hooks 配置失敗: {e}")
            return []


__all__ = ["TemplateHooksService"]

