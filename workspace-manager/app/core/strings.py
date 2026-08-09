"""String utility functions"""


def snake_case(value: str) -> str:
    """Convert camelCase or PascalCase to snake_case

    Args:
        value: String to convert

    Returns:
        String in snake_case format

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
