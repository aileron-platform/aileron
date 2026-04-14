"""Repository JSON utility functions."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def safe_json_loads(
    data: Optional[str],
    entity_id: str = "",
    entity_type: str = "entity"
) -> Dict[str, Any]:
    """安全地反序列化 JSON 字串.

    Args:
        data: JSON 字串或 None
        entity_id: 實體 ID（用於錯誤日誌）
        entity_type: 實體類型名稱（用於錯誤日誌）

    Returns:
        字典，如果 data 為 None 或解析失敗則返回空字典
    """
    if not data:
        return {}
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(
            f"Failed to deserialize {entity_type} data",
            extra={
                "error": str(e),
                f"{entity_type}_id": entity_id,
                "data_preview": data[:200] if data else None,
            }
        )
        return {}
