"""
Keycloak Profile Sync Service

Syncs user profile changes back to Keycloak via Keycloak Account REST API.
Uses user's own access token, no admin service account required.
"""

import logging
from typing import Optional

import httpx

from app.modules.auth.config import get_keycloak_config

logger = logging.getLogger(__name__)


class KeycloakProfileSync:
    """Sync profile changes back to Keycloak account API"""

    def __init__(self):
        self.config = get_keycloak_config()

    async def sync_profile_to_keycloak(
        self,
        access_token: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> bool:
        """Sync firstName/lastName back to Keycloak

        Args:
            access_token: User's access token
            first_name: New firstName (None means don't update)
            last_name: New lastName (None means don't update)

        Returns:
            True means sync succeeded, False means failed
        """
        if not self.config.enabled:
            logger.debug("Auth not enabled, skipping Keycloak profile sync")
            return True

        # Assemble fields to update
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
                # First GET current profile to preserve other fields
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

                # POST to update profile
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


# Singleton
_keycloak_profile_sync: Optional[KeycloakProfileSync] = None


def get_keycloak_profile_sync() -> KeycloakProfileSync:
    global _keycloak_profile_sync
    if _keycloak_profile_sync is None:
        _keycloak_profile_sync = KeycloakProfileSync()
    return _keycloak_profile_sync
