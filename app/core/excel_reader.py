import pandas as pd
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class ExcelData:
    columns: List[str]
    rows: List[Dict[str, str]]
    phone_column: str | None = None


def load_excel(file_path: str) -> ExcelData:
    df = pd.read_excel(file_path, dtype=str)
    df = df.fillna("")
    columns = list(df.columns)
    rows = df.to_dict(orient="records")
    phone_column = _detect_phone_column(columns)
    return ExcelData(columns=columns, rows=rows, phone_column=phone_column)


def _detect_phone_column(columns: List[str]) -> str | None:
    keywords = ["telefone", "phone", "celular", "whatsapp", "fone", "tel"]
    for col in columns:
        if any(kw in col.lower() for kw in keywords):
            return col
    return None


def render_message(template: str, row: Dict[str, str]) -> str:
    message = template
    for key, value in row.items():
        message = message.replace(f"{{{{{key}}}}}", str(value))
    return message
