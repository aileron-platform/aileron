from app.main import app


def test_gemini_settings_router_is_not_registered():
    paths = {route.path for route in app.routes}
    assert not any("/gemini" in path for path in paths)
