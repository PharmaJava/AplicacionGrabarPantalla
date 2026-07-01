# -*- coding: utf-8 -*-
"""Genera icon.ico para la aplicación (monitor con punto de grabación)."""
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Sombra suave del monitor
d.rounded_rectangle([30, 46, 230, 186], radius=22, fill=(0, 0, 0, 60))

# Cuerpo del monitor (azul oscuro)
d.rounded_rectangle([26, 40, 226, 180], radius=20, fill=(37, 52, 79, 255))
# Bisel interior
d.rounded_rectangle([38, 52, 214, 168], radius=12, fill=(18, 25, 40, 255))
# Brillo sutil de pantalla
d.rounded_rectangle([46, 60, 150, 92], radius=8, fill=(30, 42, 66, 180))

# Punto de grabación (rojo) con halo
cx, cy = 126, 110
d.ellipse([cx - 42, cy - 42, cx + 42, cy + 42], fill=(197, 34, 31, 60))
d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=(220, 45, 40, 255))
d.ellipse([cx - 12, cy - 16, cx + 2, cy - 2], fill=(255, 150, 148, 220))  # brillo

# Pie del monitor
d.rectangle([116, 180, 136, 200], fill=(37, 52, 79, 255))
d.rounded_rectangle([84, 200, 168, 216], radius=8, fill=(37, 52, 79, 255))

sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save("icon.ico", format="ICO", sizes=sizes)
print("icon.ico generado con tamaños:", sizes)
