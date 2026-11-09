"""
IDEye - Icon Generator
Generates high-resolution multi-size PNG, ICO, and ICNS assets from ideye_logo.svg.
"""

import os
import shutil
from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtCore import QRectF, QByteArray

def main():
    app = QApplication.instance() or QApplication([])

    svg_path = os.path.join("ideye", "assets", "icons", "ideye_logo.svg")
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()

    # Full squircle renderer
    renderer_full = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))

    # Transparent renderer (omit background squircle rects)
    lines = svg_content.splitlines()
    trans_lines = [
        line for line in lines
        if not (
            'fill="url(#bgGradA)"' in line
            or 'stroke="url(#sapphireBorderA)"' in line
            or "Background squircle" in line
        )
    ]
    transparent_svg = "\n".join(trans_lines)
    renderer_trans = QSvgRenderer(QByteArray(transparent_svg.encode("utf-8")))

    def render_to_pil(renderer, size):
        qimg = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        qimg.fill(0)
        p = QPainter(qimg)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(p, QRectF(0, 0, float(size), float(size)))
        p.end()

        # Convert QImage to PIL Image
        buffer = qimg.bits().asstring(qimg.sizeInBytes())
        pil_img = Image.frombuffer("RGBA", (qimg.width(), qimg.height()), buffer, "raw", "BGRA", 0, 1)
        return pil_img.copy()

    # 1. 1024x1024 full
    pil_1024 = render_to_pil(renderer_full, 1024)

    # 2. 1024x1024 transparent
    pil_trans_1024 = render_to_pil(renderer_trans, 1024)

    # 3. 256x256 full
    pil_256 = pil_1024.resize((256, 256), Image.Resampling.LANCZOS)

    # Output paths
    icons_dir = os.path.join("ideye", "assets", "icons")
    pil_1024.save(os.path.join(icons_dir, "app_icon.png"))
    pil_1024.save(os.path.join(icons_dir, "app_icon_rounded.png"))
    pil_256.save(os.path.join(icons_dir, "app_icon_256.png"))
    pil_trans_1024.save(os.path.join(icons_dir, "app_icon_transparent.png"))

    # Multi-resolution ICOs
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_path = os.path.join(icons_dir, "ideye.ico")
    pil_1024.save(ico_path, format="ICO", sizes=ico_sizes)

    ico_trans_path = os.path.join(icons_dir, "ideye_transparent.ico")
    pil_trans_1024.save(ico_trans_path, format="ICO", sizes=ico_sizes)

    # Root ideye.ico
    shutil.copy2(ico_path, "ideye.ico")

    # Root ideye.icns if supported
    try:
        pil_1024.save("ideye.icns", format="ICNS")
        print("Generated root ideye.icns")
    except Exception as e:
        print("Could not generate ideye.icns:", e)

    print("Successfully generated all icon assets:")
    print(" - ideye/assets/icons/app_icon.png (1024x1024)")
    print(" - ideye/assets/icons/app_icon_rounded.png (1024x1024)")
    print(" - ideye/assets/icons/app_icon_256.png (256x256)")
    print(" - ideye/assets/icons/app_icon_transparent.png (1024x1024)")
    print(" - ideye/assets/icons/ideye.ico (16, 24, 32, 48, 64, 128, 256)")
    print(" - ideye/assets/icons/ideye_transparent.ico (16, 24, 32, 48, 64, 128, 256)")
    print(" - ideye.ico (root)")

if __name__ == "__main__":
    main()
