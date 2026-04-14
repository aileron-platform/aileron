"""字串處理工具函數"""


def snake_case(value: str) -> str:
    """將 camelCase 或 PascalCase 轉換為 snake_case

    Args:
        value: 要轉換的字串

    Returns:
        snake_case 格式的字串

    Examples:
        >>> snake_case("firstName")
        'first_name'
        >>> snake_case("FirstName")
        'first_name'
    """
    result = []
    for index, char in enumerate(value):
        if char.isupper() and index != 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


__all__ = ["snake_case"]
