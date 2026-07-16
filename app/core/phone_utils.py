import re
from typing import List

DEFAULT_DDD = "32"


def normalize_phone(phone: str) -> str:
    """Forma canônica: só dígitos, sem 0 de operadora, sem 55, com DDD (padrão 32).

    Todos os módulos usam esta forma como chave do contato, garantindo que o
    mesmo número importado como '+55 32 9...', '032 9...' ou '9...' seja um só.
    """
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0") and len(digits) in (11, 12):
        digits = digits[1:]
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    if len(digits) in (8, 9):
        digits = DEFAULT_DDD + digits
    return digits


def to_wa_phone(phone: str) -> str:
    """Número no formato internacional do WhatsApp: 55 + DDD + número."""
    digits = normalize_phone(phone)
    if len(digits) in (10, 11):
        digits = "55" + digits
    return digits


def split_phones(raw: str) -> List[str]:
    """Divide uma célula que pode conter vários telefones separados por ; ou ,"""
    parts = re.split(r"[;,]", raw)
    return [p.strip() for p in parts if p.strip()]
