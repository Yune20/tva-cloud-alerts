"""pytest bootstrap: make the repo root importable so `import config` and
`from core.<mod> import ...` resolve when pytest runs from anywhere."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))