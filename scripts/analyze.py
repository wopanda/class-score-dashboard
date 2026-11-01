"""读成绩表(每个工作表一次考试),用代码算出全部数字,写出 analysis.json。

用法: python analyze.py 成绩表.xlsx analysis.json
表头格式: 学号, 姓名, 科目(满分N)..., 缺考说明(可选)。
"""
from __future__ import annotations

import json
import re
import statistics
import sys

import openpyxl

TIERS = [0.60, 0.70, 0.80]  # 档位:得分率
NEAR_GAP = 0.04  # 离上一档不超过 4 个百分点,算"差一点"


def parse_headers(header: list) -> tuple[list[tuple[int, str, int]], int | None]:
    """返回 [(列号, 科目, 满分)] 和缺考说明列号。"""
    subjects: list[tuple[int, str, int]] = []
    note_col = None
    for i, h in enumerate(header):
        h = str(h or "")
        m = re.match(r"(.+?)\(满分(\d+)\)", h)
        if m:
            subjects.append((i, m.group(1), int(m.group(2))))
        elif "缺考" in h:
            note_col = i
    if not subjects:
        raise ValueError("表头里没有「科目(满分N)」格式的列,无法识别科目和满分")
    return subjects, note_col


def load(path: str) -> dict:
    """读出全部考试和学生。"""
    wb = openpyxl.load_workbook(path, data_only=True)
    exams: list[str] = []
    students: dict[str, dict] = {}
    subj_names: list[str] = []
    fulls: dict[str, int] = {}
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        subjects, note_col = parse_headers(list(rows[0]))
        if not subj_names:
            subj_names = [s[1] for s in subjects]
            fulls = {s[1]: s[2] for s in subjects}
        exams.append(ws.title)
        for r in rows[1:]:
            if not r or r[0] is None:
                continue
            sid, name = str(r[0]), str(r[1])
            st = students.setdefault(sid, {"id": sid, "name": name, "exams": {}})
            vals = {n: r[i] for i, n, _ in subjects}
            note = r[note_col] if note_col is not None else None
            if any(v is None for v in vals.values()):
                st["exams"][ws.title] = {"absent": True, "note": note or "未录入成绩"}
            else:
                total = sum(vals.values())
                st["exams"][ws.title] = {
                    "absent": False,
                    "scores": vals,
                    "total": total,
                    "total_rate": round(total / sum(fulls.values()), 4),
                }
    return {"exams": exams, "subjects": subj_names, "fulls": fulls, "students": students}


def class_stats(data: dict) -> dict:
    """每次考试、每科的班级统计。缺考的人不计入。"""
    out: dict = {}
    for e in data["exams"]:
        valid = [s["exams"][e] for s in data["students"].values() if not s["exams"][e]["absent"]]
        per = {}
        for sub in data["subjects"]:
            full = data["fulls"][sub]
            xs = [v["scores"][sub] for v in valid]
            avg = statistics.mean(xs)
            per[sub] = {
                "avg": round(avg, 1),
                "rate": round(avg / full, 4),
                "max": max(xs),
                "min": min(xs),
                "std": round(statistics.pstdev(xs), 1),
                "pass_rate": round(sum(x >= 0.6 * full for x in xs) / len(xs), 4),
                "excellent_rate": round(sum(x >= 0.85 * full for x in xs) / len(xs), 4),
            }
        out[e] = {
            "n_valid": len(valid),
            "subjects": per,
            "avg_total_rate": round(statistics.mean(v["total_rate"] for v in valid), 4),
        }
    return out


def flags(data: dict, cstats: dict) -> list[dict]:
    """红黄绿名单。最新一次考试没有成绩的,标"待确认",不猜。"""
    exams = data["exams"]
    latest = exams[-1]
    res = []
    for s in data["students"].values():
        valid_exams = [e for e in exams if not s["exams"][e]["absent"]]
        item = {"id": s["id"], "name": s["name"], "absent_exams": [e for e in exams if s["exams"][e]["absent"]]}
        item["scores"] = {e: s["exams"][e]["scores"] for e in valid_exams}
        item["subject_rates"] = {
            e: {sub: round(s["exams"][e]["scores"][sub] / data["fulls"][sub], 4) for sub in data["subjects"]}
            for e in valid_exams
        }
        if latest not in valid_exams:
            item.update(level="待确认", reasons=[f"{latest}没有成绩"])
            res.append(item)
            continue
        cur = s["exams"][latest]
        rates = {sub: cur["scores"][sub] / data["fulls"][sub] for sub in data["subjects"]}
        mean_rate = statistics.mean(rates.values())
        red, yellow, green = [], [], []
        trend = [s["exams"][e]["total_rate"] for e in valid_exams]
        if len(trend) >= 3 and trend[-1] < trend[-2] < trend[-3] and trend[-3] - trend[-1] >= 0.05:
            red.append("总分连续下降")
        elif len(trend) == 2 and trend[-1] < trend[-2] - 0.03:
            red.append("总分下降")
        weak = [sub for sub, r in rates.items() if r < 0.6]
        if len(weak) >= 3:
            red.append("三科及以上低于满分的 60%:" + "、".join(weak))
        skew = [sub for sub, r in rates.items() if r < mean_rate * 0.8]
        if skew:
            yellow.append("偏科:" + "、".join(skew) + " 比本人平均低 20% 以上")
        if len(trend) >= 2 and trend[-1] - trend[0] >= 0.05:
            green.append(f"总得分率从 {trend[0] * 100:.0f}% 升到 {trend[-1] * 100:.0f}%")
        level = "红" if red else "黄" if yellow else "绿" if green else "无"
        tags = [t for t, hit in (("红", red), ("黄", yellow), ("绿", green)) if hit]
        crate = {sub: cstats[latest]["subjects"][sub]["rate"] for sub in data["subjects"]}
        diff = {sub: rates[sub] - crate[sub] for sub in data["subjects"]}
        item.update(
            level=level,
            tags=tags,
            reasons=red + yellow + green,
            latest_total_rate=cur["total_rate"],
            rates={k: round(v, 4) for k, v in rates.items()},
            strengths=sorted(diff, key=diff.get, reverse=True)[:2],
            weakest=min(diff, key=diff.get),
            trend=[{"exam": e, "total_rate": s["exams"][e]["total_rate"]} for e in valid_exams],
        )
        res.append(item)
    return res


def near_miss(fl: list[dict]) -> list[dict]:
    """总分处在中段、离上一档只差一点的学生。"""
    pool = sorted((f for f in fl if "latest_total_rate" in f), key=lambda f: -f["latest_total_rate"])
    n = len(pool)
    mid = pool[n // 4 : n - n // 4]
    out = []
    for f in mid:
        r = f["latest_total_rate"]
        nxt = next((t for t in TIERS if t > r), None)
        if nxt is None or nxt - r > NEAR_GAP:
            continue
        low = sorted(f["rates"], key=f["rates"].get)[:2]
        out.append({"id": f["id"], "name": f["name"], "rate": r, "next_tier": nxt, "gap": round(nxt - r, 4), "lowest": low})
    return out


def main(src: str, dst: str) -> None:
    data = load(src)
    cs = class_stats(data)
    fl = flags(data, cs)
    latest = data["exams"][-1]
    edges = [(0, 0.6, "60%以下"), (0.6, 0.7, "60%–70%"), (0.7, 0.8, "70%–80%"), (0.8, 0.9, "80%–90%"), (0.9, 1.01, "90%以上")]
    rates = [f["latest_total_rate"] for f in fl if "latest_total_rate" in f]
    distribution = [{"label": lb, "count": sum(lo <= r < hi for r in rates)} for lo, hi, lb in edges]
    result = {
        "distribution": distribution,
        "exams": data["exams"],
        "subjects": data["subjects"],
        "fulls": data["fulls"],
        "class": cs,
        "students": fl,
        "near_miss": near_miss(fl),
        "need_confirm": [f["id"] for f in fl if f["level"] == "待确认"],
    }
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    cnt = {k: sum(1 for f in fl if k in f.get("tags", [f["level"]])) for k in ("红", "黄", "绿", "待确认")}
    print(f"已写出 {dst}:{len(fl)} 人,{len(data['exams'])} 次考试;名单 {cnt};可提分 {len(result['near_miss'])} 人")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法: python analyze.py 成绩表.xlsx analysis.json")
    main(sys.argv[1], sys.argv[2])
