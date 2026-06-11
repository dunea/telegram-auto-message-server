"""根据 base.html 导航栏 SVG 消息气泡生成 favicon。

- 256x256 主图，主题色 #4f46e5（indigo-600，与 base.html theme-color 一致）
- 三个白色圆点 + 左下小尾巴
- 缩放为 16/32/48 三档合成多尺寸 favicon.ico
- 同时输出 favicon.svg 源文件供现代浏览器使用
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

INDIGO = (79, 70, 229, 255)  # #4f46e5
WHITE = (255, 255, 255, 255)


def draw_base(size: int = 256) -> Image.Image:
    """在透明背景上绘制消息气泡，返回 RGBA 图。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆角矩形主体（留出底部尾巴空间）
    pad = int(size * 0.08)
    bubble_box = (pad, pad, size - pad, size - pad - int(size * 0.06))
    radius = int(size * 0.22)
    draw.rounded_rectangle(bubble_box, radius=radius, fill=INDIGO)

    # 左下小尾巴（三角形）
    tail = [
        (int(size * 0.22), int(size * 0.78)),
        (int(size * 0.22), int(size * 0.92)),
        (int(size * 0.34), int(size * 0.82)),
    ]
    draw.polygon(tail, fill=INDIGO)

    # 三个白色圆点
    dot_r = int(size * 0.055)
    cy = int(size * 0.46)
    gap = int(size * 0.13)
    cx = size // 2
    for offset in (-gap, 0, gap):
        draw.ellipse(
            (cx + offset - dot_r, cy - dot_r, cx + offset + dot_r, cy + dot_r),
            fill=WHITE,
        )
    return img


def write_svg(path: Path) -> None:
    """同步输出与 ICO 视觉一致的 SVG 源文件。"""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">\n'
        '  <path fill="#4f46e5" d="M48 28a40 40 0 0 0-40 40v96a40 40 0 0 0 40 40h18v26l34-26h108a40 40 0 0 0 40-40V68a40 40 0 0 0-40-40z"/>\n'
        '  <circle cx="86"  cy="118" r="14" fill="#fff"/>\n'
        '  <circle cx="128" cy="118" r="14" fill="#fff"/>\n'
        '  <circle cx="170" cy="118" r="14" fill="#fff"/>\n'
        '</svg>\n'
    )
    path.write_text(svg, encoding="utf-8")


def main() -> None:
    base = draw_base(256)
    base.save(STATIC_DIR / "favicon-256.png", format="PNG")

    sizes = [16, 32, 48, 64, 128, 256]
    layers = [base.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]
    layers[-1].save(
        STATIC_DIR / "favicon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=layers[:-1],
    )

    write_svg(STATIC_DIR / "favicon.svg")

    for p in (STATIC_DIR / "favicon.ico", STATIC_DIR / "favicon.svg", STATIC_DIR / "favicon-256.png"):
        print(f"wrote {p} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
