"""
Keycloak Profile Sync Service

透過 Keycloak Account REST API 將使用者 Profile 變更同步回 Keycloak。
使用使用者自己的 access token，不需要 admin service account。
"""

import logging
from typing import Optional

import httpx

from app.modules.auth.config import get_keycloak_config

logger = logging.getLogger(__name__)


class KeycloakProfileSync:
    """將 Profile 變更同步回 Keycloak Account API"""

    def __init__(self):
        self.config = get_keycloak_config()

    async def sync_profile_to_keycloak(
        self,
        access_token: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> bool:
        """將 firstName/lastName 同步回 Keycloak

        Args:
            access_token: 使用者的 access token
            first_name: 新的 firstName（None 表示不更新）
            last_name: 新的 lastName（None 表示不更新）

        Returns:
            True 表示同步成功，False 表示失敗
        """
        if not self.config.enabled:
            logger.debug("Auth not enabled, skipping Keycloak profile sync")
            return True

        # 組裝要更新的欄位
        payload = {}
        if first_name is not None:
            payload["firstName"] = first_name
        if last_name is not None:
            payload["lastName"] = last_name

        if not payload:
            return True

        account_url = f"{self.config.server_url}/account"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 先 GET 當前 profile 以保留其他欄位
                get_response = await client.get(
                    account_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                )

                if get_response.is_success:
                    current_profile = get_response.json()
                    current_profile.update(payload)
                    payload = current_profile
                else:
                    logger.warning(
                        f"Failed to fetch current Keycloak profile: "
                        f"{get_response.status_code}, proceeding with partial update"
                    )

                # POST 更新 profile
                response = await client.post(
                    account_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.is_success:
                    logger.info("Profile synced to Keycloak successfully")
                    return True
                else:
                    logger.error(
                        f"Keycloak profile sync failed: "
                        f"{response.status_code} {response.text}"
                    )
                    return False

        except httpx.HTTPError as e:
            logger.error(f"Keycloak profile sync HTTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Keycloak profile sync unexpected error: {e}")
            return False


# 單例
_keycloak_profile_sync: Optional[KeycloakProfileSync] = None


def get_keycloak_profile_sync() -> KeycloakProfileSync:
    global _keycloak_profile_sync
    if _keycloak_profile_sync is None:
        _keycloak_profile_sync = KeycloakProfileSync()
    return _keycloak_profile_sync
