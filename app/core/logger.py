import csv
import os
from datetime import datetime
from typing import Optional


FIELDNAMES = ["timestamp", "nome", "telefone", "status", "motivo"]

_LOGS_DIR = os.path.join(os.environ.get("APPDATA", "."), "Saffar", "logs")


def get_log_path(excel_path: str) -> str:
    os.makedirs(_LOGS_DIR, exist_ok=True)
    basename = os.path.splitext(os.path.basename(excel_path))[0]
    return os.path.join(_LOGS_DIR, f"{basename}_log.csv")


def init_log(log_path: str) -> None:
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()


def log_result(
    log_path: str,
    nome: str,
    telefone: str,
    success: bool,
    motivo: Optional[str] = None,
) -> None:
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "nome": nome,
            "telefone": telefone,
            "status": "sucesso" if success else "falha",
            "motivo": motivo or "",
        })
