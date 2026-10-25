#!/usr/bin/env python3
"""把物理知识点对到香港 EDB 单元，生成 docs/hk-edb/hk-edb-physics.json。

用法：
    python3 scripts/build_hk_physics_mapping.py
    python3 scripts/build_hk_physics_mapping.py --check    # 只校验对照表有没有写错

初中（八、九年级）对到科学（中一至中三）14 个单元；高中对到物理课程及评估指引
必修部分的五个单元及其小节。对照关系写在 docs/hk-edb/physics-chapter-map.json。
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "docs/hk-edb" / "physics-units.json"
CHMAP = ROOT / "docs/hk-edb" / "physics-chapter-map.json"
TOPICS = ROOT / "data" / "topics.json"
OUT = ROOT / "docs/hk-edb" / "hk-edb-physics.json"
REPORT = ROOT / "docs/hk-edb" / "mapping-report-physics.md"


def chapter_key(chapter):
    return re.sub(r"\s+\d+(\.\d+)*$", "", chapter).strip()


def load_units():
    data = json.loads(UNITS.read_text(encoding="utf-8"))
    units = {}
    for u in data["junior"]["units"]:
        units[u["code"]] = dict(u, keyStage="KS3")
    for u in data["senior"]["units"]:
        units[u["code"]] = dict(u, keyStage="KS4", subtopics=u.get("subtopics", []))
        for s in u.get("subtopics", []):
            units[s["code"]] = dict(s, keyStage="KS4", parent=u["name"])
    for e in data["senior"]["electives"]:
        units[e["code"]] = dict(e, keyStage="KS4", elective=True)
    return units


def main():
    check_only = "--check" in sys.argv
    cmap = json.loads(CHMAP.read_text(encoding="utf-8"))
    units = load_units()
    topics = [t for t in json.loads(TOPICS.read_text(encoding="utf-8")) if t["id"].startswith("cnp_")]

    by_chapter = defaultdict(list)
    for t in topics:
        by_chapter[chapter_key(t["chapter"])].append(t)

    problems = []
    for band in ("junior", "senior"):
        for ch, code in (cmap.get(band) or {}).items():
            if ch not in by_chapter:
                problems.append(f"章名对不上：{ch}")
            if code and code not in units:
                problems.append(f"单元编号不存在：{code}（{ch}）")
    for key, code in (cmap.get("topic_overrides") or {}).items():
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

    overrides = cmap.get("topic_overrides") or {}
    confidence = cmap.get("confidence") or {}
    notes = cmap.get("notes") or {}

    entries = []
    for ch, items in by_chapter.items():
        band = "junior" if items[0]["grade"] <= 9 else "senior"
        default = (cmap.get(band) or {}).get(ch, "__missing__")
        for t in items:
            key = f"{ch}|{t['name']}"
            code = overrides.get(key, default)
            if code == "__missing__" or code is None:
                code, conf = None, "none"
            else:
                conf = "inferred" if key in overrides else confidence.get(ch, "exact")
            unit = units.get(code) if code else None
            entries.append({
                "topicId": t["id"],
                "topicName": t["name"],
                "grade": t["grade"],
                "chapter": ch,
                "keyStage": unit["keyStage"] if unit else None,
                "unit": code,
                "unitName": (unit.get("zh") or unit.get("name")) if unit else None,
                "unitNameEn": unit.get("name") if unit else None,
                "confidence": conf,
                "note": notes.get(ch) if conf != "exact" else None,
            })

    entries.sort(key=lambda e: (e["grade"], e["topicId"]))
    stats = Counter(e["confidence"] for e in entries)

    payload = {
        "edition": "hk_edb_physics",
        "label": "香港教育局科學／物理課程",
        "status": "draft",
        "kind": "curriculum",
        "note": ("人工编写的章 → 单元对照，再套到章内每个知识点。"
                 "初中对到科学（中一至中三）14 个单元，高中对到物理必修部分五单元及其小节。"
                 "confidence：exact 一对一明确；inferred 需要人判断；none 香港课程没有对应内容。"),
        "source": "EDB Science (S1-3) Supplement 2017；Physics C&A Guide (S4-6) 2015",
        "summary": {
            "topics": len(entries),
            "exact": stats.get("exact", 0),
            "inferred": stats.get("inferred", 0),
            "none": stats.get("none", 0),
            "chapters": len(by_chapter),
        },
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"topics {len(entries)}  exact {stats.get('exact',0)}  "
          f"inferred {stats.get('inferred',0)}  none {stats.get('none',0)}")
    print(f"-> {OUT.relative_to(ROOT)}")
    if check_only:
        return

    lines = ["# 物理课程对照报告（初稿）", "",
             f"共 {len(entries)} 个物理知识点，按 {len(by_chapter)} 个人教版章对到香港 EDB 单元。", "",
             "| 把握程度 | 知识点 | 含义 |", "| --- | ---: | --- |",
             f"| exact | {stats.get('exact',0)} | 章与单元基本一对一 |",
             f"| inferred | {stats.get('inferred',0)} | 方向对，需要人确认 |",
             f"| none | {stats.get('none',0)} | 香港课程没有对应内容 |", ""]

    by_ks = Counter(e["keyStage"] or "未对" for e in entries)
    lines += ["## 按学段分布", "", "| 学段 | 知识点 |", "| --- | ---: |"]
    for ks, n in sorted(by_ks.items()):
        lines.append(f"| {ks} | {n} |")
    lines.append("")

    used = {e["unit"] for e in entries}
    unused = [c for c in units if c not in used and not units[c].get("subtopics")]
    if unused:
        lines += ["## 没有被任何知识点对上的香港单元", ""]
        for c in unused:
            lines.append(f"- `{c}` {units[c].get('zh') or units[c]['name']}")
        lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"-> {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
