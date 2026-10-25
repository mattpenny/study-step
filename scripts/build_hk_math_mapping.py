#!/usr/bin/env python3
"""把 827 个数学知识点对到香港 EDB 学习单元，生成 docs/hk-edb/hk-edb-math.json。

用法：
    python3 scripts/build_hk_math_mapping.py            # 生成对照表 + 报告
    python3 scripts/build_hk_math_mapping.py --check    # 只校验对照表有没有写错的章名

对照关系写在 docs/hk-edb/chapter-map.json 里（人工判断）：章 → 单元，
章内个别知识点再覆盖。这个脚本只负责套用、校验、统计，不做猜测。
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "docs" / "hk-edb" / "math-learning-units.json"
CHMAP = ROOT / "docs" / "hk-edb" / "chapter-map.json"
TOPICS = ROOT / "data" / "topics.json"
OUT = ROOT / "docs" / "hk-edb" / "hk-edb-math.json"
REPORT = ROOT / "docs" / "hk-edb" / "mapping-report.md"


def chapter_key(chapter):
    """去掉小节号：「九上 第二十五章 一元二次方程 25.2」→「九上 第二十五章 一元二次方程」"""
    return re.sub(r"\s+\d+(\.\d+)*$", "", chapter).strip()


def band_of(grade):
    if grade <= 6:
        return "primary"
    if grade <= 9:
        return "junior"
    return "senior"


def load_units():
    data = json.loads(UNITS.read_text(encoding="utf-8"))
    units = {}
    for u in data["primary"]["units"]:
        units[u["code"]] = dict(u, keyStage=u["keyStage"], code=u["code"])
    for u in data["junior_secondary"]["units"]:
        units[f"S{u['unit']}"] = dict(u, keyStage="KS3", code=f"S{u['unit']}")
    for key, prefix in (("compulsory", "COM"), ("m1", "M1"), ("m2", "M2")):
        for u in data["senior_secondary"][key]:
            code = f"{prefix}{u['unit']}"
            units[code] = dict(u, keyStage="KS4", code=code, section=u.get("section", key))
    return units


def main():
    check_only = "--check" in sys.argv
    cmap = json.loads(CHMAP.read_text(encoding="utf-8"))
    units = load_units()
    topics = [t for t in json.loads(TOPICS.read_text(encoding="utf-8")) if t["id"].startswith("cnm_")]

    by_chapter = defaultdict(list)
    for t in topics:
        by_chapter[chapter_key(t["chapter"])].append(t)

    # ---- 校验：对照表里的章名、知识点名、单元编号都必须真的存在
    problems = []
    for band in ("primary", "junior", "senior"):
        for ch, code in (cmap.get(band) or {}).items():
            if ch not in by_chapter:
                problems.append(f"章名对不上：{ch}")
            if code and code not in units:
                problems.append(f"单元编号不存在：{code}（{ch}）")
    for band in ("primary", "junior", "senior"):
        for key, code in (cmap.get(f"{band}_topic_overrides") or {}).items():
            ch, _, name = key.partition("|")
            if ch not in by_chapter:
                problems.append(f"覆盖里的章名对不上：{ch}")
            elif name not in {t["name"] for t in by_chapter[ch]}:
                problems.append(f"覆盖里的知识点对不上：{ch} / {name}")
            if code and code not in units:
                problems.append(f"覆盖里的单元编号不存在：{code}")

    if problems:
        print("对照表有问题：")
        for p in dict.fromkeys(problems):
            print("  -", p)
        sys.exit(1)

    # ---- 套用
    overrides = {}
    for band in ("primary", "junior", "senior"):
        overrides.update(cmap.get(f"{band}_topic_overrides") or {})
    confidence = cmap.get("confidence", {})
    notes = {}
    for band in ("primary", "junior", "senior"):
        notes.update(cmap.get(f"{band}_notes") or {})

    entries = []
    for ch, items in by_chapter.items():
        band = band_of(items[0]["grade"])
        default = (cmap.get(band) or {}).get(ch, "__missing__")
        for t in items:
            key = f"{ch}|{t['name']}"
            code = overrides.get(key, default)
            if code == "__missing__" or code is None:
                code, conf = None, "none"
            else:
                conf = "inferred" if key in overrides else confidence.get(ch, "inferred")
            unit = units.get(code) if code else None
            entries.append({
                "topicId": t["id"],
                "topicName": t["name"],
                "grade": t["grade"],
                "chapter": ch,
                "keyStage": unit["keyStage"] if unit else None,
                "strand": unit["strand"] if unit else None,
                "unit": code,
                "unitName": unit["name"] if unit else None,
                "confidence": conf,
                "note": notes.get(ch) if conf != "exact" else None,
            })

    entries.sort(key=lambda e: (e["grade"], e["topicId"]))
    stats = Counter(e["confidence"] for e in entries)

    payload = {
        "edition": "hk_edb_math",
        "label": "香港教育局數學課程（2017 學習內容）",
        "status": "draft",
        "kind": "curriculum",
        "note": ("這是「課程對照」，不是教材版本對照，所以不放 data/mappings/："
                 "那個目錄的 schema 是給人教版以外教科書用的（topicId/grade/term/unit/chapter）。"
                 "人工編寫的章 → 單元對照，再套到章內每個知識點。"
                 "confidence：exact 一對一明確；inferred 需要人判斷；none 香港課程沒有對應內容（unit 為 null）。"
                 "對照依據見 docs/hk-edb/chapter-map.json。"),
        "source": "EDB《數學教育學習領域課程指引補充文件：學習內容》（2017，中文版）",
        "method": "以人教版章為單位對到香港學習單元；一章跨多個單元時在章內逐個知識點覆蓋",
        "summary": {
            "topics": len(entries),
            "exact": stats.get("exact", 0),
            "inferred": stats.get("inferred", 0),
            "none": stats.get("none", 0),
            "chapters": len(by_chapter),
        },
        "entries": entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"topics {len(entries)}  exact {stats.get('exact',0)}  "
          f"inferred {stats.get('inferred',0)}  none {stats.get('none',0)}")
    print(f"-> {OUT.relative_to(ROOT)}")
    if check_only:
        return

    # ---- 报告
    lines = ["# 香港课程对照报告（初稿）", "",
             f"共 {len(entries)} 个数学知识点，按 {len(by_chapter)} 个人教版章对到香港 EDB 学习单元。", "",
             "| 把握程度 | 知识点 | 含义 |", "| --- | ---: | --- |",
             f"| exact | {stats.get('exact',0)} | 章与单元基本一对一，可直接用 |",
             f"| inferred | {stats.get('inferred',0)} | 方向对，但需要人确认 |",
             f"| none | {stats.get('none',0)} | 香港课程没有对应内容 |", ""]

    none_by_ch = Counter(e["chapter"] for e in entries if e["confidence"] == "none")
    if none_by_ch:
        lines += ["## 香港课程没有对应内容的部分", "", "| 章 | 知识点数 | 说明 |", "| --- | ---: | --- |"]
        for ch, n in none_by_ch.most_common():
            lines.append(f"| {ch} | {n} | {notes.get(ch, '')} |")
        lines.append("")

    by_ks = Counter(e["keyStage"] or "未对" for e in entries)
    lines += ["## 按学段分布", "", "| 学段 | 知识点 |", "| --- | ---: |"]
    for ks, n in sorted(by_ks.items()):
        lines.append(f"| {ks} | {n} |")
    lines.append("")

    used = {e["unit"] for e in entries}
    unused = [c for c in units if c not in used]
    if unused:
        lines += ["## 没有被任何知识点对上的香港单元", "",
                  "这些单元在香港课程里有，但人教版没有直接对应的知识点，反过来提示可以补充内容：", ""]
        for c in unused:
            lines.append(f"- `{c}` {units[c]['name']}")
        lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"-> {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
