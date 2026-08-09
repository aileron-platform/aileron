from collections.abc import Callable
from pathlib import Path

_MOUNTINFO_ESCAPES = {
    "\\040": " ",
    "\\011": "\t",
    "\\012": "\n",
    "\\134": "\\",
}


def contains_nested_mount(
    source_path: str | Path,
    *,
    error_factory: Callable[[str], Exception],
    read_error_message: str,
    invalid_error_message: str,
) -> bool:
    try:
        source = Path(source_path).resolve(strict=True)
        mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    except (OSError, RuntimeError) as exc:
        raise error_factory(read_error_message) from exc

    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) < 5:
            raise error_factory(invalid_error_message)
        mountpoint = fields[4]
        for encoded, decoded in _MOUNTINFO_ESCAPES.items():
            mountpoint = mountpoint.replace(encoded, decoded)
        try:
            Path(mountpoint).resolve(strict=False).relative_to(source)
        except ValueError:
            continue
        return True
    return False
