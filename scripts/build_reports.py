"""每位学生一份给家长的个人学习报告(单文件网页,A4 可打印)。

用法: python build_reports.py analysis.json comments.json 输出目录 [--class 初二(3)班] [--teacher 班主任姓名] [--date 2026年11月]
报告里只有这位同学自己的情况和班级平均水平,没有别的同学的信息,没有名单标记,没有排名。
"""
from __future__ import annotations

import argparse
import json
import os

from common import AMBER, BLUE, GREEN, GREY, esc, line_chart, pct, radar

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#e9eeec;color:#1f2a37;font:14.5px/1.75 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.page{width:794px;max-width:100%;margin:18px auto;background:#fff;border-radius:6px;box-shadow:0 6px 24px rgba(20,40,60,.12);overflow:hidden}
.top{background:linear-gradient(120deg,#1f6b57,#2f6fb1);color:#fff;padding:26px 34px}
.top small{opacity:.85;letter-spacing:2px}.top h1{margin:4px 0 2px;font-size:30px}.top p{margin:0;opacity:.9;font-size:13.5px}
.body{padding:20px 34px 26px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.tile{background:#f1f6f3;border-radius:12px;padding:10px 12px}.tile span{font-size:12.5px;color:#66717f}.tile b{display:block;font-size:21px;line-height:1.35;color:#1f6b57}
.tile b.up{color:#2f8a57}.tile b.dn{color:#c4453a}
h2{font-size:16px;margin:20px 0 8px;color:#1f6b57;display:flex;align-items:center;gap:8px}h2::before{content:"";width:5px;height:16px;border-radius:3px;background:linear-gradient(#2f6fb1,#1f6b57)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:center}.cap{text-align:center;font-size:12.5px;color:#66717f}
.legend{display:flex;gap:14px;justify-content:center;font-size:12px;color:#66717f}.legend i{display:inline-block;width:13px;height:4px;border-radius:2px;margin-right:4px;vertical-align:middle}
table{border-collapse:collapse;width:100%;font-size:13.5px}th{color:#66717f;font-weight:500;padding:6px 4px;border-bottom:2px solid #e3e9ed}
td{padding:7px 4px;border-bottom:1px solid #edf1f4;text-align:center}td.s{text-align:left;font-weight:600}
.mini{display:inline-block;width:80px;height:8px;border-radius:4px;background:#edf1f4;vertical-align:middle;overflow:hidden}.mini i{display:block;height:100%;background:linear-gradient(90deg,#2f6fb1,#1f6b57)}
.up{color:#2f8a57}.dn{color:#c4453a}.fl0{color:#8d98a5}
.cm{border-radius:12px;padding:10px 14px;margin:8px 0}.cm b{display:block;font-size:13px;margin-bottom:1px}
.c1{background:#e9f5ee}.c1 b{color:#2f8a57}.c2{background:#fcf3e1}.c2 b{color:#a8741a}.c3{background:#eaf1fa}.c3 b{color:#2f6fb1}.c4{background:#f3f0f8}.c4 b{color:#6b4ea0}
.foot{display:flex;justify-content:space-between;margin-top:22px;padding-top:12px;border-top:1px dashed #cfd7dd;color:#66717f;font-size:13px}
.note{color:#8d98a5;font-size:12px;margin-top:10px}
@media print{body{background:#fff}.page{box-shadow:none;margin:0;border-radius:0;width:auto}@page{size:A4;margin:8mm}h2,.cm,.two{break-inside:avoid}}
@media (max-width:640px){.tiles{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}.top,.body{padding-left:18px;padding-right:18px}}
"""


def delta_html(d: float | None) -> str:
    """变化(百分点)的箭头文字。"""
    if d is None:
        return '<span class="fl0">—</span>'
    if d > 0.5:
        return f'<span class="up">▲ {d:.1f}</span>'
    if d < -0.5:
        return f'<span class="dn">▼ {abs(d):.1f}</span>'
    return '<span class="fl0">基本持平</span>'


def build(A: dict, s: dict, c: dict | None, cls: str, teacher: str, date: str) -> str:
    """生成一位同学的报告网页。"""
    ex, subs, fulls, cl = A["exams"], A["subjects"], A["fulls"], A["class"]
    full_total = sum(fulls.values())
    valid = [e for e in ex if e in s["scores"]]
    tot = {e: sum(s["scores"][e].values()) / full_total for e in valid}
    trend_vals = [tot.get(e) for e in ex]
    class_vals = [cl[e]["avg_total_rate"] for e in ex]
    date_part = (" · " + esc(date)) if date else ""
    head = f'<div class="top"><small>学习成长报告</small><h1>{esc(s["name"])} 同学</h1><p>{esc(cls)} · {esc(ex[0])} 至 {esc(ex[-1])}{date_part}</p></div>'
    if not valid:
        return page(head + '<div class="body"><p>暂时没有这位同学的成绩记录。</p></div>', s)

    cur = valid[-1]
    rates = s["subject_rates"][cur]
    prev = valid[-2] if len(valid) >= 2 else None
    d_tot = (tot[cur] - tot[prev]) * 100 if prev else None
    best2 = sorted(subs, key=lambda k: -rates[k])[:2]
    weak = min(subs, key=lambda k: rates[k])
    tile_d = "—" if d_tot is None else "基本持平" if abs(d_tot) <= 0.5 else f'{"▲" if d_tot > 0 else "▼"} {abs(d_tot):.1f} 个百分点'
    tile_cls = "" if d_tot is None else "up" if d_tot > 0.5 else "dn" if d_tot < -0.5 else ""
    tiles = (
        f'<div class="tile"><span>最近一次总得分率</span><b>{pct(tot[cur])}</b></div>'
        f'<div class="tile"><span>比上一次</span><b class="{tile_cls}">{tile_d}</b></div>'
        f'<div class="tile"><span>较强的两科</span><b>{esc("、".join(best2))}</b></div>'
        f'<div class="tile"><span>下阶段重点</span><b style="color:#a8741a">{esc(weak)}</b></div>'
    )

    r_chart = radar(
        subs,
        [
            {"values": [cl[cur]["subjects"][k]["rate"] for k in subs], "stroke": GREY, "fill": "rgba(141,152,165,.18)", "width": 1.8},
            {"values": [rates[k] for k in subs], "stroke": BLUE, "fill": "rgba(47,111,177,.28)"},
        ],
        250,
    )
    t_chart = line_chart(
        ex,
        [{"values": class_vals, "color": GREY, "dashed": True, "name": "班级平均水平"}, {"values": trend_vals, "color": BLUE, "name": f"{s['name']}"}],
        360,
        200,
        0.4,
        1.0,
    )

    head_cells = "".join(f"<th>{esc(e)}</th>" for e in ex)
    rows = ""
    for k in subs:
        cells = ""
        for e in ex:
            cells += f"<td>{s['scores'][e][k]}</td>" if e in s["scores"] else '<td style="color:#8d98a5">缺考</td>'
        first, lastv = s["subject_rates"][valid[0]][k], rates[k]
        d = (lastv - first) * 100 if len(valid) > 1 else None
        rows += f'<tr><td class="s">{esc(k)}<small style="color:#8d98a5;font-weight:400"> /{fulls[k]}</small></td>{cells}<td><span class="mini"><i style="width:{rates[k] * 100:.0f}%"></i></span> {pct(rates[k])}</td><td>{delta_html(d)}</td></tr>'
    tcells = "".join(f"<td><b>{sum(s['scores'][e].values())}</b></td>" if e in s["scores"] else '<td style="color:#8d98a5">缺考</td>' for e in ex)
    d_all = (tot[cur] - tot[valid[0]]) * 100 if len(valid) > 1 else None
    rows += f'<tr style="background:#f6f9f8"><td class="s">总分<small style="color:#8d98a5;font-weight:400"> /{full_total}</small></td>{tcells}<td><span class="mini"><i style="width:{tot[cur] * 100:.0f}%"></i></span> {pct(tot[cur])}</td><td>{delta_html(d_all)}</td></tr>'
    table = f'<table><tr><th style="text-align:left">科目</th>{head_cells}<th>最近一次得分率</th><th>与第一次相比(个百分点)</th></tr>{rows}</table>'
    miss = ""
    if s["absent_exams"]:
        miss = f'<p class="note">{esc("、".join(s["absent_exams"]))}缺考,该次不计入趋势和变化。</p>'

    if c:
        comment = (
            f'<div class="cm c1"><b>做得好的地方</b>{esc(c["strength"])}</div>'
            f'<div class="cm c2"><b>下一步可以加强</b>{esc(c["improve"])}</div>'
            f'<div class="cm c3"><b>老师想对你说</b>{esc(c["message"])}</div>'
            + (f'<div class="cm c4"><b>家校配合小建议</b>{esc(c["home"])}</div>' if c.get("home") else "")
        )
    else:
        comment = '<div class="cm c3"><b>老师评语</b>待老师补充</div>'

    body = f"""<div class="body">
<div class="tiles">{tiles}</div>
<h2>各科发展</h2><div class="two"><div>{r_chart}<div class="legend"><span><i style="background:{BLUE}"></i>{esc(s["name"])}</span><span><i style="background:{GREY}"></i>班级平均水平</span></div><div class="cap">{esc(cur)}</div></div><div>{t_chart}<div class="cap">总得分率的变化</div></div></div>
<h2>每次考试的分数</h2>{table}{miss}
<h2>老师的话</h2>{comment}
<div class="foot"><span>班主任:{esc(teacher) or "　　　　"}</span><span>家长签字:　　　　　　　</span></div>
<p class="note">得分率 = 得分 ÷ 满分。本报告只呈现 {esc(s["name"])} 同学自己的情况和班级平均水平,评语为老师的草稿。</p></div>"""
    return page(head + body, s)


def page(inner: str, s: dict) -> str:
    """包上网页外壳。"""
    return f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(s["name"])} 学习成长报告</title><style>{CSS}</style></head><body><div class="page">{inner}</div></body></html>'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis")
    ap.add_argument("comments")
    ap.add_argument("outdir")
    ap.add_argument("--class", dest="cls", default="班级")
    ap.add_argument("--teacher", default="")
    ap.add_argument("--date", default="")
    a = ap.parse_args()
    with open(a.analysis, encoding="utf-8") as f:
        A = json.load(f)
    C = {}
    if os.path.exists(a.comments):
        with open(a.comments, encoding="utf-8") as f:
            C = json.load(f)
    os.makedirs(a.outdir, exist_ok=True)
    for s in A["students"]:
        c = (C.get("students") or {}).get(s["id"])
        path = os.path.join(a.outdir, f'{s["id"]}-{s["name"]}.html')
        with open(path, "w", encoding="utf-8") as f:
            f.write(build(A, s, c, a.cls, a.teacher, a.date))
    print(f"已写出 {len(A['students'])} 份报告到 {a.outdir}")


if __name__ == "__main__":
    main()
