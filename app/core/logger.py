import csv
import os
from datetime import datetime
from typing import Optional


FIELDNAMES = ["timestamp", "nome", "telefone", "status", "motivo"]


def get_log_path(excel_path: str) -> str:
    base = os.path.splitext(excel_path)[0]
    return f"{base}_log.csv"


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
