"""班主任用的班级成绩分析看板(单文件网页,只给班主任看,不要发给家长)。

用法: python build_class.py analysis.json comments.json 输出.html [--title 初二(3)班] [--reports 学生报告]
学生姓名会链接到 <reports>/<学号>-<姓名>.html(由 build_reports.py 生成)。
"""
from __future__ import annotations

import argparse
import json
import os

from common import AMBER, BLUE, GREEN, GREY, GRID, RED, esc, heat, line_chart, pct

CSS = """
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(#eef3f1,#f6f8f7 360px);color:#1f2a37;font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:22px 16px 70px}
.hero{background:linear-gradient(120deg,#1f6b57,#2f6fb1);color:#fff;border-radius:20px;padding:26px 28px;box-shadow:0 10px 30px rgba(31,107,87,.22)}
.hero h1{margin:0 0 4px;font-size:27px;letter-spacing:.5px}.hero p{margin:0;opacity:.88}
.hero .tag{display:inline-block;margin-top:12px;background:rgba(255,255,255,.18);border-radius:20px;padding:1px 12px;font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}
.kpi{background:#fff;border-radius:14px;padding:12px 14px;box-shadow:0 2px 10px rgba(20,40,60,.06);border-left:5px solid var(--c)}
.kpi b{display:block;font-size:25px;line-height:1.3;color:var(--c)}.kpi span{color:#66717f;font-size:13px}
section{background:#fff;border-radius:16px;padding:18px 20px;margin:16px 0;box-shadow:0 2px 12px rgba(20,40,60,.06)}
h2{margin:0 0 4px;font-size:18px;color:#1f6b57}.desc{margin:0 0 14px;color:#6b7684;font-size:13.5px}
.bar{display:grid;grid-template-columns:52px 1fr 230px;gap:10px;align-items:center;margin:9px 0}
.bar .tr{height:20px;border-radius:10px;background:#edf1f4;position:relative;overflow:hidden}
.bar .fl{height:100%;border-radius:10px;background:linear-gradient(90deg,#2f6fb1,#1f6b57)}
.bar b{font-size:15px}.bar small{color:#66717f;font-size:12.5px}
.sp{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.spc{border:1px solid #e8edf1;border-radius:12px;padding:8px 12px}.spc h3{margin:0;font-size:15px;display:flex;justify-content:space-between}
.up{color:#2f8a57}.dn{color:#c4453a}.fl0{color:#8d98a5}
.legend{display:flex;gap:16px;justify-content:center;font-size:12.5px;color:#66717f;margin-top:2px}.legend i{display:inline-block;width:14px;height:4px;border-radius:2px;margin-right:5px;vertical-align:middle}
table{border-collapse:separate;border-spacing:3px;width:100%;font-size:13px}th{color:#66717f;font-weight:500;padding:4px}
td{text-align:center;padding:5px 4px;border-radius:6px;color:#16202b}td.nm{background:none;text-align:left;white-space:nowrap}
td.nm a{color:#2f6fb1;text-decoration:none;font-weight:500}td.nm a:hover{text-decoration:underline}
.scroll{max-height:460px;overflow:auto}
.lists{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px}
.lst{border-radius:14px;padding:12px 14px;background:var(--bg)}.lst h3{margin:0 0 8px;font-size:15.5px;color:var(--c)}
.chip{display:block;background:#fff;border-radius:10px;padding:7px 11px;margin:6px 0;text-decoration:none;color:#1f2a37;box-shadow:0 1px 4px rgba(20,40,60,.06)}
.chip b{color:var(--c)}.chip small{display:block;color:#66717f;font-size:12.5px;line-height:1.5}
.nm2 td,.nm2 th{text-align:left;padding:6px 8px;border-bottom:1px solid #eef1f4;border-radius:0}.nm2{border-spacing:0}
.sum{background:#eef6f2;border-radius:12px;padding:12px 16px}.sum ol{margin:8px 0 0;padding-left:20px}
.note{color:#8d98a5;font-size:12.5px;text-align:center;margin-top:24px}
"""


def build(analysis: dict, comments: dict | None, title: str, reports: str) -> str:
    """生成网页字符串。"""
    A = analysis
    ex, subs, last = A["exams"], A["subjects"], A["exams"][-1]
    cl = A["class"]
    L = cl[last]["subjects"]
    by_rate = sorted(subs, key=lambda s: -L[s]["rate"])
    sts = A["students"]
    red = [s for s in sts if "红" in s.get("tags", [])]
    yel = [s for s in sts if "黄" in s.get("tags", [])]
    grn = [s for s in sts if "绿" in s.get("tags", [])]

    def link(s: dict) -> str:
        return f'{esc(reports)}/{esc(s["id"])}-{esc(s["name"])}.html'

    kpi = [
        ("全班平均得分率", pct(cl[last]["avg_total_rate"]), BLUE),
        ("相对最强的科目", by_rate[0], GREEN),
        ("相对最弱的科目", by_rate[-1], AMBER),
        ("需要重点关注", f"{len(red)} 人", RED),
        ("可提分的中段学生", f'{len(A["near_miss"])} 人', GREEN),
        ("待确认", f'{len(A["need_confirm"])} 人', GREY),
    ]
    kpis = "".join(f'<div class="kpi" style="--c:{c}"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for k, v, c in kpi)

    bars = "".join(
        f'<div class="bar"><b>{s}</b><div class="tr"><div class="fl" style="width:{L[s]["rate"] * 100:.1f}%"></div></div>'
        f'<small><b>{pct(L[s]["rate"])}</b> · 平均 {L[s]["avg"]}/{A["fulls"][s]} · 及格 {pct(L[s]["pass_rate"])} · 优秀 {pct(L[s]["excellent_rate"])}</small></div>'
        for s in by_rate
    )

    spark = ""
    for s in subs:
        vals = [cl[e]["subjects"][s]["rate"] for e in ex]
        d = (vals[-1] - vals[0]) * 100
        cls, sign = ("up", "▲") if d > 0.5 else ("dn", "▼") if d < -0.5 else ("fl0", "—")
        chart = line_chart(ex, [{"values": vals, "color": BLUE, "name": s}], 300, 120, 0.55, 0.8, (0.6, 0.7), True, False)
        spark += f'<div class="spc"><h3><span>{s}</span><span class="{cls}">{sign} {abs(d):.1f} 个百分点</span></h3>{chart}</div>'

    dist = A["distribution"]
    mx = max(d["count"] for d in dist) or 1
    bw, gap, H = 70, 26, 170
    svg = [f'<svg viewBox="0 0 {len(dist) * (bw + gap) + gap} {H + 40}" width="100%">']
    for i, d in enumerate(dist):
        h = (H - 30) * d["count"] / mx
        x = gap + i * (bw + gap)
        svg.append(f'<rect x="{x}" y="{H - h:.1f}" width="{bw}" height="{h:.1f}" rx="8" fill="url(#g)"/>')
        svg.append(f'<text x="{x + bw / 2}" y="{H - h - 7:.1f}" text-anchor="middle" font-weight="700" font-size="15" fill="{GREEN}">{d["count"]}</text>')
        svg.append(f'<text x="{x + bw / 2}" y="{H + 20}" text-anchor="middle" font-size="12" fill="{GREY}">{esc(d["label"])}</text>')
    svg.append(f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{GREEN}"/></linearGradient></defs></svg>')

    rows = ""
    for s in sorted(sts, key=lambda s: -(s.get("latest_total_rate") or 0)):
        nm = f'<td class="nm"><a href="{link(s)}" target="_blank">{esc(s["name"])}</a></td>'
        if "rates" not in s:
            rows += f'<tr>{nm}<td colspan="{len(subs) + 1}" style="color:#8d98a5">{esc(s["reasons"][0])}</td></tr>'
            continue
        cells = "".join(f'<td style="background:{heat(s["rates"][k])}">{pct(s["rates"][k])}</td>' for k in subs)
        rows += f'{"<tr>"}{nm}{cells}<td style="background:{heat(s["latest_total_rate"])};font-weight:700">{pct(s["latest_total_rate"])}</td></tr>'
    heat_tbl = f'<table><tr><th style="text-align:left">姓名</th>{"".join(f"<th>{k}</th>" for k in subs)}<th>总分</th></tr>{rows}</table>'

    def chips(xs: list[dict], c: str) -> str:
        if not xs:
            return '<small style="color:#8d98a5">暂无</small>'
        return "".join(
            f'<a class="chip" style="--c:{c}" href="{link(s)}" target="_blank"><b>{esc(s["name"])}</b><small>{esc("；".join(s["reasons"]))}</small></a>' for s in xs
        )

    lists = (
        f'<div class="lst" style="--c:{RED};--bg:#fbeeec"><h3>需要重点关注({len(red)})</h3>{chips(red, RED)}</div>'
        f'<div class="lst" style="--c:#a8741a;--bg:#fcf3e1"><h3>偏科({len(yel)})</h3>{chips(yel, AMBER)}</div>'
        f'<div class="lst" style="--c:#2f8a57;--bg:#e9f5ee"><h3>进步明显({len(grn)})</h3>{chips(grn, "#2f8a57")}</div>'
    )
    if A["need_confirm"]:
        byid = {s["id"]: s for s in sts}
        lists += f'<div class="lst" style="--c:{GREY};--bg:#f0f2f4"><h3>待老师确认({len(A["need_confirm"])})</h3>{chips([byid[i] for i in A["need_confirm"]], GREY)}</div>'

    near = "暂无"
    if A["near_miss"]:
        byid = {s["id"]: s for s in sts}
        near = '<table class="nm2"><tr><th>姓名</th><th>总得分率</th><th>离上一档</th><th>较弱的两科</th></tr>' + "".join(
            f'<tr><td><a href="{link(byid[n["id"]])}" target="_blank" style="color:#2f6fb1;text-decoration:none">{esc(n["name"])}</a></td><td>{pct(n["rate"], 1)}</td>'
            f'<td>差 {n["gap"] * 100:.1f} 个百分点到 {pct(n["next_tier"])}</td><td>{esc("、".join(n["lowest"]))}</td></tr>'
            for n in A["near_miss"]
        ) + "</table>"

    summ = '<p style="color:#8d98a5;margin:0">待老师补充</p>'
    if comments and comments.get("summary"):
        adv = "".join(f"<li>{esc(a)}</li>" for a in comments.get("advice", []))
        summ = f'<div class="sum"><p style="margin:0">{esc(comments["summary"])}</p><ol>{adv}</ol></div>'

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}成绩分析看板</title><style>{CSS}</style></head><body><div class="wrap">
<div class="hero"><h1>{esc(title)}成绩分析看板</h1><p>{esc(" → ".join(ex))} · 共 {len(sts)} 人</p><span class="tag">仅供班主任使用,不要发给家长</span></div>
<div class="kpis">{kpis}</div>
<section><h2>各科得分率</h2><p class="desc">{esc(last)},从强到弱。得分率 = 平均分 ÷ 满分。</p>{bars}</section>
<section><h2>各科三次考试的变化</h2><p class="desc">全班平均得分率。看哪一科在进步,哪一科在回落。</p><div class="sp">{spark}</div></section>
<section><h2>全班总分分布</h2><p class="desc">{esc(last)},按总得分率分段的人数。</p>{"".join(svg)}</section>
<section><h2>成绩热力图</h2><p class="desc">{esc(last)}。红色偏弱,绿色偏强。点姓名打开这位同学给家长的报告。</p><div class="scroll">{heat_tbl}</div></section>
<section><h2>需要关注的名单</h2><p class="desc">规则见 SKILL.md。一位同学可以同时出现在几个名单里。点姓名打开他的报告。</p><div class="lists">{lists}</div></section>
<section><h2>可提分的中段学生</h2><p class="desc">总分在中间一半,离上一档不超过 4 个百分点。</p>{near}</section>
<section><h2>小结和建议</h2>{summ}</section>
<p class="note">数字由程序从成绩表计算;评语和建议是草稿,请老师核对后再使用。</p>
</div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis")
    ap.add_argument("comments")
    ap.add_argument("out")
    ap.add_argument("--title", default="班级")
    ap.add_argument("--reports", default="学生报告")
    a = ap.parse_args()
    with open(a.analysis, encoding="utf-8") as f:
        analysis = json.load(f)
    comments = None
    if os.path.exists(a.comments):
        with open(a.comments, encoding="utf-8") as f:
            comments = json.load(f)
    page = build(analysis, comments, a.title, a.reports)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"已写出 {a.out}({len(page) // 1024} KB)")


if __name__ == "__main__":
    main()
