import re
import pandas as pd
from dataclasses import dataclass, field
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
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    unidade_col = next((c for c in df.columns if c.strip().lower() == "unidade"), None)
    if unidade_col:
        df[unidade_col] = df[unidade_col].mask(df[unidade_col] == "").ffill().fillna("")
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


@dataclass
class UnidadeInadimplente:
    unidade: str
    competencias: List[str] = field(default_factory=list)
    total: str = ""


def parse_inadimplentes(file_path: str) -> Dict[str, UnidadeInadimplente]:
    """Parse a relatório de inadimplentes Excel and return a dict keyed by unit number."""
    try:
        df = pd.read_excel(file_path, header=None, dtype=str).fillna("")
    except Exception as e:
        raise ValueError(f"Não foi possível ler o arquivo: {e}")

    if df.empty:
        raise ValueError("O arquivo está vazio.")

    result: Dict[str, UnidadeInadimplente] = {}
    current: Optional[UnidadeInadimplente] = None
    compet_idx: Optional[int] = None
    total_idx: Optional[int] = None
    in_data = False

    for _, row in df.iterrows():
        cells = [str(c).strip() for c in row]
        first = cells[0] if cells else ""

        m = re.match(r'^(\d{3,6})\s*-\s*(.+)', first)
        if m:
            if current:
                result[current.unidade] = current
            current = UnidadeInadimplente(unidade=m.group(1).strip())
            compet_idx = None
            total_idx = None
            in_data = False
            continue

        if any("Compet" in c for c in cells):
            try:
                compet_idx = next(i for i, c in enumerate(cells) if "Compet" in c)
                total_idx = next(i for i, c in enumerate(reversed(cells)) if c == "Total")
                total_idx = len(cells) - 1 - total_idx
            except StopIteration:
                pass
            in_data = True
            continue

        if not current or not in_data:
            continue

        non_empty = [(i, c) for i, c in enumerate(cells) if c]
        if non_empty and non_empty[0][1] == "Total":
            if total_idx is not None and total_idx < len(cells) and cells[total_idx]:
                current.total = cells[total_idx]
            elif non_empty:
                current.total = non_empty[-1][1]
            continue

        if compet_idx is not None and compet_idx < len(cells):
            comp = cells[compet_idx]
            if re.match(r'\d{2}/\d{4}', comp):
                current.competencias.append(comp)

    if current:
        result[current.unidade] = current

    return result


def render_message(template: str, row: Dict[str, str]) -> str:
    message = template
    for key, value in row.items():
        safe = "" if value is None else str(value)
        message = message.replace(f"{{{{{key}}}}}", safe)
    return message
