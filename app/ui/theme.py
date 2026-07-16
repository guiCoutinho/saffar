"""Paleta e constantes visuais compartilhadas entre as abas.

Hierarquia de botões: ação primária usa a cor do tema (verde da marca);
secundárias são cinza; destrutivas são cinza com hover vermelho.
"""

GREEN_OK = "#23A55A"
RED_ERR = "#D9534F"
ORANGE_WARN = "#E8A23D"

BTN_SECONDARY = ("gray72", "gray29")
BTN_SECONDARY_HOVER = ("gray62", "gray35")
BTN_DANGER_HOVER = ("#C0392B", "#8F2B20")


def secondary(**overrides) -> dict:
    """Kwargs de estilo para botões secundários."""
    style = {"fg_color": BTN_SECONDARY, "hover_color": BTN_SECONDARY_HOVER}
    style.update(overrides)
    return style


def danger(**overrides) -> dict:
    """Kwargs de estilo para botões destrutivos (cinza, hover vermelho)."""
    style = {"fg_color": BTN_SECONDARY, "hover_color": BTN_DANGER_HOVER}
    style.update(overrides)
    return style
