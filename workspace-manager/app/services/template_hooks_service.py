"""Template Hooks ConfigurationService"""

from __future__ import annotations

import json
import logging
from typing import Optional, List

from sqlalchemy.orm import Session
import yaml

from app.models import HooksConfigResponse, HooksConfigUpdateRequest
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateHooksService(TemplateBaseService):
    """Handle template hooks configuration management"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def _get_hooks_dir(self, template_id: str):
        return self._resolve_template_dir(template_id) / "hooks"

    def get_hooks_config(self, template_id: str) -> Optional[HooksConfigResponse]:
        """Get template hooks configuration"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None

        hooks_dir = self._get_hooks_dir(template_id)
        if not hooks_dir.exists():
            return HooksConfigResponse(template_id=template_id, hooks={})

        try:
            hooks_map = {}
            for hook_file in sorted(hooks_dir.glob("*.yaml")):
                hook_data = yaml.safe_load(hook_file.read_text(encoding="utf-8")) or {}
                event_name = hook_data.get("event")
                if not event_name:
                    continue
                matcher = hook_data.get("matcher", "*")
                if isinstance(matcher, dict):
                    matcher = matcher.get("tool") or matcher.get("path") or "*"
                action = hook_data.get("action", {})
                hooks_map.setdefault(event_name, []).append(
                    {
                        "matcher": matcher,
                        "hooks": [
                            {
                                "type": action.get("type", "command"),
                                "command": action.get("command") or action.get("path") or "",
                                "timeout": hook_data.get("timeout", 30),
                            }
                        ],
                    }
                )
            return HooksConfigResponse(template_id=template_id, hooks=hooks_map)
        except Exception as e:
            logger.error(f"Failed to read hooks configuration: {e}")
            return HooksConfigResponse(template_id=template_id, hooks={})

    def update_hooks_config(
        self, template_id: str, payload: HooksConfigUpdateRequest
    ) -> Optional[HooksConfigResponse]:
        """Update template hooks configuration"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None

        hooks_dir = self._get_hooks_dir(template_id)
        hooks_dir.mkdir(parents=True, exist_ok=True)
        try:
            for existing_file in hooks_dir.glob("*.yaml"):
                existing_file.unlink()

            for event_name, rules in payload.hooks.items():
                for rule_index, rule in enumerate(rules):
                    for hook_index, hook_exec in enumerate(rule.hooks):
                        hook_payload = {
                            "id": f"{event_name}-{rule_index}-{hook_index}",
                            "event": event_name,
                            "matcher": {"tool": rule.matcher},
                            "action": {
                                "type": hook_exec.type,
                                "command": hook_exec.command,
                            },
                            "timeout": hook_exec.timeout,
                        }
                        (hooks_dir / f"{event_name}-{rule_index}-{hook_index}.yaml").write_text(
                            yaml.safe_dump(hook_payload, allow_unicode=True, sort_keys=False),
                            encoding="utf-8",
                        )
            logger.info(f"Updated hooks configuration for template {template_id}")
            return HooksConfigResponse(template_id=template_id, hooks=payload.hooks)
        except Exception as e:
            logger.error(f"Failed to update hooks configuration: {e}")
            raise

    def load_hooks(self, template_id: str) -> List:
        """Load Hooks Configuration"""
        from app.models.template import TemplateHook

        hooks_dir = self._get_hooks_dir(template_id)
        if not hooks_dir.exists():
            return []

        try:
            hooks = []
            for hook_file in sorted(hooks_dir.glob("*.yaml")):
                hook_data = yaml.safe_load(hook_file.read_text(encoding="utf-8")) or {}
                matcher = hook_data.get("matcher", "*")
                if isinstance(matcher, dict):
                    matcher = matcher.get("tool") or matcher.get("path") or "*"
                action = hook_data.get("action", {})
                hooks.append(TemplateHook(
                    id=hook_data.get("id") or hook_file.stem,
                    name=hook_data.get("name") or hook_file.stem,
                    event=hook_data.get("event", ""),
                    matcher=matcher,
                    action=action.get("type", "command"),
                    command=action.get("command") or action.get("path"),
                    timeout=hook_data.get("timeout", 30),
                ))

            return hooks
        except Exception as e:
            logger.error(f"Load Hooks ConfigurationFailed: {e}")
            return []


__all__ = ["TemplateHooksService"]
