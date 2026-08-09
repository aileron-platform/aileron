"""Localization module interface tests."""

from app.modules.localization.translator import get_i18n_service


def test_localization_module_loads_owned_translations() -> None:
    get_i18n_service.cache_clear()

    translator = get_i18n_service()

    assert {"en", "zh-TW"}.issubset(set(translator.supported_languages))
    assert translator.translate("access_denied", language="en") != "access_denied"
