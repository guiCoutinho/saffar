import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class ExcelData:
    columns: List[str]
    rows: List[Dict[str, str]]
    phone_column: str | None = None


def preview_excel(file_path: str, nrows: int = 15) -> List[List[str]]:
    """Return the first `nrows` raw rows (no header assumed) as lists of strings."""
    df = pd.read_excel(file_path, header=None, nrows=nrows, dtype=str)
    df = df.fillna("")
    return [list(row) for row in df.itertuples(index=False, name=None)]


def load_excel(file_path: str, header_row: int = 0, phone_column: Optional[str] = None) -> ExcelData:
    df = pd.read_excel(file_path, header=header_row, dtype=str)
    df = df.fillna("")
    # Drop completely empty columns (unnamed artifacts above the real header)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    columns = list(df.columns)
    rows = df.to_dict(orient="records")
    if phone_column is None:
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
