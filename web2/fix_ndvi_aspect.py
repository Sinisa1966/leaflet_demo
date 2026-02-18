#!/usr/bin/env python3
"""
Ispravlja omjer NDVI slike da odgovara granicama parcele 1427/2.
Parcel: width/height = 0.875 (lng 0.0035 / lat 0.004)
"""
from pathlib import Path
from PIL import Image

WEB2_DATA = Path(__file__).resolve().parent / "data"
PARCEL_RATIO = (21.2021 - 21.1986) / (44.8182 - 44.8142)  # ≈ 0.875


def fix_aspect(img_path: Path) -> None:
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size
    current_ratio = w / h

    if abs(current_ratio - PARCEL_RATIO) < 0.01:
        print("Omjer već OK")
        return

    if current_ratio > PARCEL_RATIO:
        # Slika je preširoka – cropuj po sredini
        new_w = int(h * PARCEL_RATIO)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        # Slika je previsoka – cropuj po sredini
        new_h = int(w / PARCEL_RATIO)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    img.save(img_path, "PNG")
    print(f"Ispravljeno: {img.size[0]}x{img.size[1]} (ratio {img.size[0]/img.size[1]:.4f})")


if __name__ == "__main__":
    p = WEB2_DATA / "ndvi_1427_2.png"
    if p.exists():
        fix_aspect(p)
    else:
        print(f"Fajl ne postoji: {p}")
