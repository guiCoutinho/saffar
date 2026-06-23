import re


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)
