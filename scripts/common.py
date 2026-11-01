"""两个网页共用的小工具:格式化、颜色、折线图和雷达图(纯 SVG,不依赖任何外部库)。"""
from __future__ import annotations

import html
import math

GREEN = "#1f6b57"
BLUE = "#2f6fb1"
AMBER = "#e39a2d"
RED = "#c4453a"
GREY = "#8d98a5"
GRID = "#e5eaee"


def esc(s: object) -> str:
    """HTML 转义。"""
    return html.escape(str(s), quote=True)


def pct(x: float, digits: int = 0) -> str:
    """0.6987 -> '70%'。"""
    return f"{x * 100:.{digits}f}%"


def heat(r: float) -> str:
    """得分率 -> 从红到绿的柔和底色。"""
    t = max(0.0, min(1.0, (r - 0.4) / 0.5))
    return f"hsl({round(t * 125)},58%,{78 - round(t * 6)}%)"


def _smooth(pts: list[tuple[float, float]]) -> str:
    """把几个点连成平滑曲线(Catmull-Rom 转贝塞尔)。"""
    if len(pts) == 1:
        return f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def line_chart(
    labels: list[str],
    series: list[dict],
    width: int = 420,
    height: int = 190,
    ymin: float = 0.4,
    ymax: float = 1.0,
    ticks: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9),
    point_labels: bool = True,
    legend: bool = True,
) -> str:
    """折线图。series: [{values: [float|None], color, dashed?, name}]。None 表示缺考,断开不画。"""
    pl, pr, pt, pb = 38, 34, 18, 30
    iw, ih = width - pl - pr, height - pt - pb

    def X(i: int) -> float:
        return pl + (iw * i / (len(labels) - 1) if len(labels) > 1 else iw / 2)

    def Y(v: float) -> float:
        return pt + ih * (1 - (v - ymin) / (ymax - ymin))

    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for t in ticks:
        out.append(f'<line x1="{pl}" x2="{width - pr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{GRID}"/>')
        out.append(f'<text x="{pl - 6}" y="{Y(t) + 4:.1f}" text-anchor="end" font-size="10.5" fill="{GREY}">{round(t * 100)}%</text>')
    for i, lb in enumerate(labels):
        out.append(f'<text x="{X(i):.1f}" y="{height - 8}" text-anchor="middle" font-size="11" fill="{GREY}">{esc(lb)}</text>')
    for si, s in enumerate(series):
        pts = [(X(i), Y(v)) for i, v in enumerate(s["values"]) if v is not None]
        if not pts:
            continue
        dash = ' stroke-dasharray="5 4"' if s.get("dashed") else ""
        w = 2 if s.get("dashed") else 3
        if len(pts) > 1:
            out.append(f'<path d="{_smooth(pts)}" fill="none" stroke="{s["color"]}" stroke-width="{w}" stroke-linecap="round"{dash}/>')
        if not s.get("dashed"):
            for i, v in enumerate(s["values"]):
                if v is None:
                    continue
                out.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="4.5" fill="#fff" stroke="{s["color"]}" stroke-width="2.5"/>')
                if point_labels:
                    out.append(f'<text x="{X(i):.1f}" y="{Y(v) - 10:.1f}" text-anchor="middle" font-size="11.5" font-weight="600" fill="{s["color"]}">{round(v * 100)}%</text>')
    out.append("</svg>")
    if legend:
        items = "".join(
            f'<span><i style="background:{s["color"]};{"opacity:.55" if s.get("dashed") else ""}"></i>{esc(s["name"])}</span>' for s in series
        )
        out.append(f'<div class="legend">{items}</div>')
    return "".join(out)


def radar(axes: list[str], series: list[dict], size: int = 260) -> str:
    """雷达图。series: [{values: [0~1], stroke, fill, name}]。"""
    n = len(axes)
    cx = cy = size / 2
    R = size / 2 - 38

    def pt(i: int, r: float) -> tuple[float, float]:
        a = -math.pi / 2 + i * 2 * math.pi / n
        return cx + R * r * math.cos(a), cy + R * r * math.sin(a)

    out = [f'<svg viewBox="0 0 {size} {size}" width="100%" role="img">']
    for g in (0.25, 0.5, 0.75, 1.0):
        out.append(f'<polygon points="{" ".join("%.1f,%.1f" % pt(i, g) for i in range(n))}" fill="none" stroke="{GRID}"/>')
    for i in range(n):
        x, y = pt(i, 1.0)
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        lx, ly = pt(i, 1.2)
        out.append(f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="middle" font-size="12.5" fill="#3b4654">{esc(axes[i])}</text>')
    for s in series:
        poly = " ".join("%.1f,%.1f" % pt(i, v) for i, v in enumerate(s["values"]))
        out.append(f'<polygon points="{poly}" fill="{s["fill"]}" stroke="{s["stroke"]}" stroke-width="{s.get("width", 2.5)}" stroke-linejoin="round"/>')
    out.append("</svg>")
    return "".join(out)
