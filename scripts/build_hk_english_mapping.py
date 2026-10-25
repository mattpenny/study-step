#!/usr/bin/env python3
"""把英语知识点对到香港 EDB 的英国语文课程结构，生成 docs/hk-edb/hk-edb-english.json。

用法：
    python3 scripts/build_hk_english_mapping.py

和数学、物理不同，香港的英国语文课程**没有规定学习单元**：它由三个学习范畴
（Interpersonal / Knowledge / Experience）、各学习阶段的學習目標，以及学校自行
设计的 modules → units → tasks 组成（见 ELE KLACG 2017 与 Primary ELCG 2025 第 2.3.2 节）。

所以这里对的是「学习阶段 + 学习范畴 + 语言焦点」，不是单元。这是结构对齐，
不是内容逐条比对；香港哪个年级教哪个语法点由学校和教科书决定，课程文件不指定。
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOPICS = ROOT / "data" / "topics.json"
OUT = ROOT / "docs/hk-edb" / "hk-edb-english.json"
REPORT = ROOT / "docs/hk-edb" / "mapping-report-english.md"

# 三个学习范畴（ELE KLA Curriculum Guide 2017, 2.2.1）
STRAND = {
    "语音": ("Knowledge", "phonics / letter-sound knowledge"),
    "词汇": ("Knowledge", "vocabulary"),
    "语法": ("Knowledge", "language forms and communicative functions"),
    "读写": ("Knowledge", "reading and writing skills"),
    "日常表达": ("Interpersonal", "communicative functions in everyday contexts"),
}


def key_stage(grade):
    if grade <= 3:
        return "KS1"      # P1–P3
    if grade <= 6:
        return "KS2"      # P4–P6
    if grade <= 9:
        return "KS3"      # S1–S3
    return "KS4"          # S4–S6


def stage_label(ks):
    return {"KS1": "P1–P3", "KS2": "P4–P6", "KS3": "S1–S3", "KS4": "S4–S6"}[ks]


def main():
    topics = [t for t in json.loads(TOPICS.read_text(encoding="utf-8")) if t["id"].startswith("cne_")]
    entries = []
    for t in topics:
        ks = key_stage(t["grade"])
        strand, focus = STRAND.get(t["domain"], ("Knowledge", t["domain"]))
        entries.append({
            "topicId": t["id"],
            "topicName": t["name"],
            "grade": t["grade"],
            "chapter": t["chapter"],
            "keyStage": ks,
            "stageYears": stage_label(ks),
            "strand": strand,
            "languageFocus": focus,
            "domain": t["domain"],
            "confidence": "structural",
        })

    entries.sort(key=lambda e: (e["grade"], e["topicId"]))
    by_ks = Counter(e["keyStage"] for e in entries)
    by_strand = Counter(e["strand"] for e in entries)

    payload = {
        "edition": "hk_edb_english",
        "label": "香港教育局英國語文課程",
        "status": "draft",
        "kind": "curriculum-structural",
        "note": ("香港英國語文課程沒有規定學習單元，只有三個學習範疇、各學習階段的學習目標，"
                 "以及學校自訂的 modules → units → tasks。所以這份對照只給「學習階段 + 學習範疇 + 語言焦點」，"
                 "不是單元對照。confidence 一律為 structural。"),
        "source": "CDC English Language Education KLA Curriculum Guide (P1–S6) 2017；Primary English Language Curriculum Guide (P1–6) 2025",
        "summary": {
            "topics": len(entries),
            "byKeyStage": dict(sorted(by_ks.items())),
            "byStrand": dict(sorted(by_strand.items())),
        },
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"topics {len(entries)}  by KS {dict(sorted(by_ks.items()))}")
    print(f"-> {OUT.relative_to(ROOT)}")

    lines = ["# 英语课程对照报告（初稿）", "",
             f"共 {len(entries)} 个英语知识点。", "",
             "**香港的英国语文课程不规定学习单元。** 它由三个学习范畴、各学习阶段的",
             "学习目标，以及学校自行设计的 modules → units → tasks 组成（ELE KLACG 2017 第 2.3.2 节）。",
             "所以这份对照只能给到「学习阶段 + 学习范畴 + 语言焦点」，无法像数学、物理那样对到单元。", "",
             "## 按学习阶段", "", "| 学习阶段 | 年级 | 知识点 |", "| --- | --- | ---: |"]
    for ks in ("KS1", "KS2", "KS3", "KS4"):
        lines.append(f"| {ks} | {stage_label(ks)} | {by_ks.get(ks, 0)} |")
    lines += ["", "## 按学习范畴", "", "| 范畴 | 知识点 |", "| --- | ---: |"]
    for s, n in sorted(by_strand.items()):
        lines.append(f"| {s} | {n} |")
    lines += ["", "## 和数学、物理对照片的差别", "",
              "- 数学、物理有官方学习单元，能对到 `1N1`、`PHY-IIb` 这种编号；英语没有。",
              "- 英语的年级对齐是结构性的：香港 KS1 = P1–P3、KS2 = P4–P6、KS3 = S1–S3、KS4 = S4–S6。",
              "- 至于「哪个语法点在哪一年教」，香港课程文件不指定，由学校和教科书决定；",
              "  要逐点对齐，只能拿某套香港教科书（例如 Longman / Oxford / Pearson 的系列）做版本对照，",
              "  那种表才适合放 `data/mappings/`。", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"-> {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
