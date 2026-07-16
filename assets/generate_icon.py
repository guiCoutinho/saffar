"""Gera o ícone do Saffar (assets/icon.ico e assets/icon.png).

Conceito: balão de conversa com um avião de papel — mensagem sendo enviada —
sobre um degradê verde que remete ao WhatsApp sem copiar a marca.

Uso: python assets/generate_icon.py
"""
import os

from PIL import Image, ImageDraw

SIZE = 1024
ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))

# Degradê do fundo (topo -> base) e verde do avião
GRAD_TOP = (47, 208, 104)
GRAD_BOTTOM = (13, 128, 96)
PLANE_GREEN = (16, 147, 95)
WHITE = (255, 255, 255)


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _rounded_square_gradient(size: int, margin: int, radius: int) -> Image.Image:
    """Quadrado arredondado preenchido com degradê vertical."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGB", (size, size))
    px = grad.load()
    inner = size - 2 * margin
    for y in range(size):
        t = min(max((y - margin) / max(inner, 1), 0.0), 1.0)
        row_color = _lerp(GRAD_TOP, GRAD_BOTTOM, t)
        for x in range(size):
            px[x, y] = row_color
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (margin, margin, size - margin, size - margin), radius=radius, fill=255
    )
    img.paste(grad, (0, 0), mask)
    return img


def _draw_bubble(draw: ImageDraw.ImageDraw) -> None:
    """Balão de conversa branco com rabinho no canto inferior esquerdo."""
    draw.rounded_rectangle((200, 240, 824, 700), radius=140, fill=WHITE)
    draw.polygon([(300, 640), (300, 855), (490, 690)], fill=WHITE)


def _draw_plane(draw: ImageDraw.ImageDraw) -> None:
    """Avião de papel (ícone clássico de enviar) dentro do balão."""
    box_x, box_y, box_w, box_h = 330, 325, 440, 295
    material = [(2, 3), (23, 12), (2, 21), (2, 14), (17, 12), (2, 10)]
    points = [
        (box_x + mx / 24 * box_w, box_y + my / 24 * box_h)
        for mx, my in material
    ]
    draw.polygon(points, fill=PLANE_GREEN)


def main():
    img = _rounded_square_gradient(SIZE, margin=64, radius=232)
    draw = ImageDraw.Draw(img)
    _draw_bubble(draw)
    _draw_plane(draw)

    png_path = os.path.join(ASSETS_DIR, "icon.png")
    ico_path = os.path.join(ASSETS_DIR, "icon.ico")
    img.resize((256, 256), Image.LANCZOS).save(png_path)
    img.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Gerados: {png_path} e {ico_path}")


if __name__ == "__main__":
    main()
