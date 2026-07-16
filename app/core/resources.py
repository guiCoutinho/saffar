import os
import sys
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource_path(relative: str) -> str:
    """Resolve um recurso empacotado: pasta _MEIPASS no .exe, raiz do repo em dev."""
    base = getattr(sys, "_MEIPASS", _ROOT)
    return os.path.join(base, relative)


def icon_path() -> Optional[str]:
    path = resource_path(os.path.join("assets", "icon.ico"))
    return path if os.path.exists(path) else None
