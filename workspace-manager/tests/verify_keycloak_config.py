"""
Keycloak Configuration Test - Force Reload Configuration

Used to verify .env file configuration is loaded correctly
"""

import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    print("=" * 60)
    print("🔧 Keycloak Configuration Verification (Force Reload)")
    print("=" * 60)

    # Load environment variables directly
    from dotenv import load_dotenv
    from pathlib import Path

    env_path = Path(__file__).parent.parent / ".env"
    print(f"\nLoading environment variables: {env_path}")
    print(f"File exists: {env_path.exists()}")

    if env_path.exists():
        load_dotenv(env_path)
        print("✅ Environment variables loaded")
    else:
        print("❌ .env file does not exist")
        return False

    # Verify environment variables
    import os
    print(f"\nEnvironment variables:")
    print(f"   ENABLE_AUTH: {os.getenv('ENABLE_AUTH')}")
    print(f"   KEYCLOAK_REALM: {os.getenv('KEYCLOAK_REALM')}")
    print(f"   KEYCLOAK_CLIENT_ID: {os.getenv('KEYCLOAK_CLIENT_ID')}")

    # Clear module cache
    if 'app.modules.auth.config' in sys.modules:
        del sys.modules['app.modules.auth.config']

    # Clear cache for all app.modules submodules
    modules_to_delete = [k for k in sys.modules.keys() if k.startswith('app.modules.auth')]
    for module in modules_to_delete:
        del sys.modules[module]

    # Re-import configuration module
    from app.modules.auth.config import reload_keycloak_config

    # Force reload configuration
    config = reload_keycloak_config()

    print("\nConfiguration info:")
    print(f"   ✅ Auth enabled: {config.enabled}")
    print(f"   ✅ Server URL: {config.server_url}")
    print(f"   ✅ Realm: {config.realm}")
    print(f"   ✅ Client ID: {config.client_id}")
    print(f"   ✅ JWKS URL: {config.jwks_url}")

    # Verify configuration
    if not config.enabled:
        print("\n   ❌ Authentication not enabled")
        return False

    if not config.server_url:
        print("\n   ❌ Server URL not configured")
        return False

    if not config.realm:
        print("\n   ❌ Realm not configured")
        return False

    if not config.client_id:
        print("\n   ❌ Client ID not configured")
        return False

    print("\n✅ All configuration verifications passed!")
    print(f"\n📝 Test accounts:")
    print(f"   - Admin: admin / admin123")
    print(f"   - User: testuser / test123")
    print(f"\n🔗 Keycloak Admin Console:")
    print(f"   - URL: http://localhost:8080/admin")
    print(f"   - Realm: {config.realm}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
