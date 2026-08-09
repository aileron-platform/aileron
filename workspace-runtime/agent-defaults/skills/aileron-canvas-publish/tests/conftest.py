from __future__ import annotations

import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
CI_ROOT = SKILL_ROOT / "assets" / "user-site-repo" / "ci"
sys.path.insert(0, str(SCRIPTS_ROOT))
sys.path.insert(1, str(CI_ROOT))
