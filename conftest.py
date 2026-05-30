import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in [
    ROOT / "packages" / "shared",
    ROOT / "apps" / "api" / "services",
    ROOT / "apps" / "api" / "data",
]:
    sys.path.insert(0, str(p))
