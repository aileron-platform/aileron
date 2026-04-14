"""
Keycloak 配置測試 - 強制重新載入配置

用於驗證 .env 文件配置是否正確載入
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    print("=" * 60)
    print("🔧 Keycloak 配置驗證（強制重新載入）")
    print("=" * 60)

    # 直接載入環境變數
    from dotenv import load_dotenv
    from pathlib import Path

    env_path = Path(__file__).parent.parent / ".env"
    print(f"\n載入環境變數: {env_path}")
    print(f"文件存在: {env_path.exists()}")

    if env_path.exists():
        load_dotenv(env_path)
        print("✅ 環境變數已載入")
    else:
        print("❌ .env 文件不存在")
        return False

    # 驗證環境變數
    import os
    print(f"\n環境變數:")
    print(f"   ENABLE_AUTH: {os.getenv('ENABLE_AUTH')}")
    print(f"   KEYCLOAK_REALM: {os.getenv('KEYCLOAK_REALM')}")
    print(f"   KEYCLOAK_CLIENT_ID: {os.getenv('KEYCLOAK_CLIENT_ID')}")

    # 清除模組緩存
    if 'app.modules.auth.config' in sys.modules:
        del sys.modules['app.modules.auth.config']

    # 清除所有 app.modules 子模組的緩存
    modules_to_delete = [k for k in sys.modules.keys() if k.startswith('app.modules.auth')]
    for module in modules_to_delete:
        del sys.modules[module]

    # 重新導入配置模組
    from app.modules.auth.config import reload_keycloak_config

    # 強制重新載入配置
    config = reload_keycloak_config()

    print("\n配置信息:")
    print(f"   ✅ 認證啟用: {config.enabled}")
    print(f"   ✅ 伺服器 URL: {config.server_url}")
    print(f"   ✅ Realm: {config.realm}")
    print(f"   ✅ Client ID: {config.client_id}")
    print(f"   ✅ JWKS URL: {config.jwks_url}")

    # 驗證配置
    if not config.enabled:
        print("\n   ❌ 認證未啟用")
        return False

    if not config.server_url:
        print("\n   ❌ 伺服器 URL 未配置")
        return False

    if not config.realm:
        print("\n   ❌ Realm 未配置")
        return False

    if not config.client_id:
        print("\n   ❌ Client ID 未配置")
        return False

    print("\n✅ 所有配置驗證通過！")
    print(f"\n📝 測試帳號：")
    print(f"   - Admin: admin / admin123")
    print(f"   - User: testuser / test123")
    print(f"\n🔗 Keycloak Admin Console:")
    print(f"   - URL: http://localhost:8080/admin")
    print(f"   - Realm: {config.realm}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
