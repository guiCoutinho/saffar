import re
import unicodedata
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


def _detect_name_column(columns: List[str]) -> Optional[str]:
    keywords = ["nome", "name", "cliente", "contato", "contact"]
    for col in columns:
        if any(kw in col.lower() for kw in keywords):
            return col
    return None


@dataclass
class UnidadeInadimplente:
    unidade: str
    competencias: List[str] = field(default_factory=list)
    total: str = ""


# Identificador da unidade: um ou mais "tokens" (letras, dígitos, acentos)
# ligados por espaço, traço, ponto ou barra. Cobre "302", "A-302", "302-B",
# "BL1-101" e também formatos com espaços/bloco como "08 B Escandinavia".
# O separador interno é UM espaço (ou um traço/ponto/barra) por vez, de modo
# que um traço-com-espaço ao redor (" - ") nunca é engolido pela unidade e
# permanece disponível como divisor entre unidade e nome.
_UNIT_TOKEN = r'\w+(?:(?:\s+|[-./])\w+)*'

# Linha de cabeçalho de unidade no relatório: "302 - Nome", "A-302 - Nome",
# "302-B - Nome", "08 B Escandinavia - Nome" etc. O separador entre unidade e
# nome precisa de espaço em pelo menos um lado para não confundir com o traço
# interno da unidade (ex.: "A-302"), que nunca tem espaço ao redor.
_UNIT_HEADER_RE = re.compile(
    r'^(' + _UNIT_TOKEN + r')(?:\s+-\s*|\s*-\s+)(.+)'
)
# Formato antigo, apenas dígitos, aceito mesmo sem espaços ("302-Nome").
_UNIT_HEADER_NUM_RE = re.compile(r'^(\d{3,6})\s*-\s*(.+)')


def _match_unit_header(text: str) -> Optional[re.Match]:
    # Exige ao menos um dígito na unidade (descarta títulos/frases) e limita o
    # tamanho para não capturar linhas de texto longas que tenham um " - ".
    m = _UNIT_HEADER_RE.match(text)
    if m and any(ch.isdigit() for ch in m.group(1)) and len(m.group(1)) <= 40:
        return m
    return _UNIT_HEADER_NUM_RE.match(text)


def normalize_unidade(value: str) -> str:
    """Normaliza a unidade para comparação: sem acentos, maiúsculas, sem
    espaços ou separadores e sem zeros à esquerda ("a - 0302" -> "A302",
    "08 B Escandinávia" -> "8BESCANDINAVIA"). Remover acentos evita que uma
    grafia com acento no relatório e outra sem acento no cadastro (ou o
    contrário) deixem de casar."""
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r'[\s\-./]', '', value).upper()
    return re.sub(r'\d+', lambda m: m.group(0).lstrip('0') or '0', value)


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

        m = _match_unit_header(first)
        if m:
            if current:
                result[normalize_unidade(current.unidade)] = current
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
        result[normalize_unidade(current.unidade)] = current

    return result


_PLACEHOLDER_RE = re.compile(r"\{\{(.+?)\}\}")


def render_message(template: str, row: Dict[str, str]) -> str:
    """Substitui {{coluna}} pelos valores da linha em UMA única passagem.

    O passo único evita que um valor de célula que contenha literalmente
    '{{outra_coluna}}' seja reinterpretado como placeholder numa iteração
    seguinte. Placeholders sem coluna correspondente são mantidos como estão.
    """
    def _repl(m):
        key = m.group(1)
        if key in row:
            value = row[key]
            return "" if value is None else str(value)
        return m.group(0)

    return _PLACEHOLDER_RE.sub(_repl, template)
