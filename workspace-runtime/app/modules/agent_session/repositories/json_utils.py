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
    """Safely deserialize JSON string.

    Args:
        data: JSON string or None
        entity_id: Entity ID (for error logging)
        entity_type: Entity type name (for error logging)

    Returns:
        Dictionary, returns empty dict if data is None or parsing fails
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
