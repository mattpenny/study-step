#!/usr/bin/env python3
"""把内地课程结构的知识点重建成「香港教育局（EDB）课程结构」。

用法：
    python3 scripts/build_hk_dataset.py
    python3 scripts/build_hk_dataset.py --dry-run   # 只统计，不写文件

做三件事：
1. 每个知识点重新挂到 EDB 的学习阶段 / 范畴 / 学习单元上，删掉人教版的
   chapter（「一年级上册 第1单元」）和内地课标编号（cms-/ces-/cps-）；
2. 数学里香港课程确实没有的 59 个知识点整条删掉，连同它的题目和先修边；
3. 生成 data/edb-standards.json，用 EDB 学习单元代替内地的课程标准条目。

产物（覆盖原文件，原始版本在 git 历史里）：
    data/topics.json
    data/questions.json
    data/dependencies.json
    data/id-aliases.json
    data/edb-standards.json
    data/hk-structure.json      阶段 / 范畴 / 单元的分层，给界面用
"""
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HK = ROOT / "docs" / "hk-edb"

DRY = "--dry-run" in sys.argv


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- 阶段定义
# 香港的年级：小一至小六、中一至中六。EDB 的初中与高中学习单元不指定年级，
# 所以初中、高中各作为一个阶段，不硬塞到某一年级里。
STAGES = OrderedDict([
    ("P1", dict(label="小一", short="小一", keyStage="KS1", grade=1, band="primary")),
    ("P2", dict(label="小二", short="小二", keyStage="KS1", grade=2, band="primary")),
    ("P3", dict(label="小三", short="小三", keyStage="KS1", grade=3, band="primary")),
    ("P4", dict(label="小四", short="小四", keyStage="KS2", grade=4, band="primary")),
    ("P5", dict(label="小五", short="小五", keyStage="KS2", grade=5, band="primary")),
    ("P6", dict(label="小六", short="小六", keyStage="KS2", grade=6, band="primary")),
    ("P1-P3", dict(label="小一至小三", short="KS1", keyStage="KS1", grade=1, band="primary")),
    ("P4-P6", dict(label="小四至小六", short="KS2", keyStage="KS2", grade=4, band="primary")),
    ("S1-S3", dict(label="中一至中三", short="初中", keyStage="KS3", grade=7, band="junior")),
    ("S4-S6", dict(label="中四至中六", short="高中", keyStage="KS4", grade=10, band="senior")),
])

# 香港数学课程的范畴（小学五个，初中三个，高中沿用初中）
MATH_PRIMARY_STRANDS = ["數", "代數", "度量", "圖形與空間", "數據處理"]
MATH_SECONDARY_STRANDS = ["數與代數", "度量", "圖形與空間", "數據處理"]


def stage_of_math(entry, primary_units):
    """数学：小学单元编号首字即年级（1N1 → 小一）；初中、高中不指定年级。"""
    unit = entry.get("unit")
    ks = entry.get("keyStage")
    if ks in ("KS1", "KS2"):
        meta = primary_units.get(unit)
        year = meta.get("year") if meta else None
        if year is None and unit and unit[0].isdigit():
            year = int(unit[0])
        return "P%d" % year if year else "P1"
    if ks == "KS3":
        return "S1-S3"
    return "S4-S6"


def stage_of_physics(entry):
    unit = entry.get("unit") or ""
    if unit.startswith("PHY"):
        return "S4-S6"
    return "S1-S3"


def stage_of_english(entry):
    return {"KS1": "P1-P3", "KS2": "P4-P6", "KS3": "S1-S3", "KS4": "S4-S6"}.get(
        entry.get("keyStage"), "S1-S3")


# ---------------------------------------------------------------- 主流程
def main():
    topics = load(DATA / "topics.json")
    questions = load(DATA / "questions.json")
    deps = load(DATA / "dependencies.json")
    alias_doc = load(DATA / "id-aliases.json") if (DATA / "id-aliases.json").exists() else {}
    aliases = alias_doc.get("aliases", {}) if isinstance(alias_doc, dict) else {}

    math_map = {e["topicId"]: e for e in load(HK / "hk-edb-math.json")["entries"]}
    phy_map = {e["topicId"]: e for e in load(HK / "hk-edb-physics.json")["entries"]}
    eng_map = {e["topicId"]: e for e in load(HK / "hk-edb-english.json")["entries"]}
    units_doc = load(HK / "math-learning-units.json")
    primary_units = {u["code"]: u for u in units_doc["primary"]["units"]}
    js_units = {("S%d" % u["unit"]): u for u in units_doc["junior_secondary"]["units"]}
    ss_units = {}
    for section, lst in units_doc["senior_secondary"].items():
        for u in lst:
            prefix = {"compulsory": "COM", "m1": "M1", "m2": "M2"}[section]
            ss_units["%s%d" % (prefix, u["unit"])] = u

    out_topics = []
    dropped = []
    by_subject = Counter()

    for t in topics:
        tid = t["id"]
        subject = "math" if tid.startswith("cnm_") else "physics" if tid.startswith("cnp_") else "english"
        by_subject[subject] += 1

        if subject == "math":
            entry = math_map.get(tid)
            if not entry or not entry.get("unit"):
                dropped.append((tid, t["name"], (entry or {}).get("note") or "香港課程沒有對應內容"))
                continue
            stage = stage_of_math(entry, primary_units)
            unit, unit_name = entry["unit"], entry["unitName"]
            strand = entry.get("strand") or ""
            if stage.startswith("P") and strand == "數與代數":
                strand = "數"          # 小学数学分成「數」和「代數」两个范畴
            confidence = entry.get("confidence", "inferred")
            std_id = "edb-math:%s" % unit
        elif subject == "physics":
            entry = phy_map.get(tid)
            if not entry or not entry.get("unit"):
                dropped.append((tid, t["name"], "香港課程沒有對應內容"))
                continue
            stage = stage_of_physics(entry)
            unit, unit_name = entry["unit"], entry["unitName"]
            strand = "物理"
            confidence = entry.get("confidence", "inferred")
            std_id = "edb-physics:%s" % unit
        else:
            entry = eng_map.get(tid)
            if not entry:
                dropped.append((tid, t["name"], "沒有對應的 EDB 學習範疇"))
                continue
            stage = stage_of_english(entry)
            strand = entry.get("strand") or ""
            unit = "%s-%s" % (stage, strand) if strand else stage
            unit_name = entry.get("languageFocus") or strand
            confidence = "inferred"      # 英語只有結構對齊，沒有單元
            std_id = "edb-english:%s" % unit

        stage_meta = STAGES[stage]
        topic = {
            "id": tid,
            "name": t["name"],
            "subject": subject,
            "stage": stage,
            "stageLabel": stage_meta["label"],
            "keyStage": stage_meta["keyStage"],
            "grade": stage_meta["grade"],          # 只用于排序，不代表年级
            "semester": "全",
            "strand": strand,
            "domain": strand if subject != "english" else (entry.get("domain") or strand),
            "unit": unit,
            "unitName": unit_name,
            "chapter": "%s %s" % (unit, unit_name),
            "type": t.get("type"),
            "description": t.get("description"),
            "mastery_criteria": t.get("mastery_criteria"),
            "diagnostic_question": t.get("diagnostic_question"),
            "external": t.get("external", False),
            "standards": [{"id": std_id, "confidence": confidence}],
        }
        for extra in ("root_reason", "mathLinks"):
            if extra in t:
                topic[extra] = t[extra]
        out_topics.append(topic)

    keep_ids = {t["id"] for t in out_topics}

    out_questions = [q for q in questions if q.get("topicId") in keep_ids]
    out_deps = [e for e in deps
                if e.get("topicId") in keep_ids and e.get("prerequisiteId") in keep_ids]

    # 内地教材的顺序未必等于香港：有的先修在香港课程里反而更晚
    # （例如「大数的改写」在人教版四年级、「小数的近似」也在四年级，
    # 但香港把大数放在小五 5N1、小数近似放在小四 4N8）。
    # 学习路径是按阶段从低到高排的，先修比本知识点更晚会让排序自相矛盾，
    # 所以这类边直接去掉，并在报告里列出来。
    grade_of = {t["id"]: t["grade"] for t in out_topics}
    kept_edges, dropped_edges = [], []
    for e in out_deps:
        if grade_of[e["prerequisiteId"]] > grade_of[e["topicId"]]:
            dropped_edges.append(e)
        else:
            kept_edges.append(e)
    out_deps = kept_edges
    dropped_ids = {d[0] for d in dropped}
    kept_aliases = {k: v for k, v in aliases.items()
                    if k not in dropped_ids
                    and all(x in keep_ids for x in (v.get("targets") or []))}
    out_alias_doc = dict(alias_doc)
    out_alias_doc["aliases"] = kept_aliases

    # ---- EDB 学习单元表（替代内地课标） ----
    std_items = {}
    for t in out_topics:
        sid = t["standards"][0]["id"]
        if sid in std_items:
            std_items[sid]["topicCount"] += 1
            continue
        std_items[sid] = {
            "id": sid,
            "subject": t["subject"],
            "keyStage": t["keyStage"],
            "strand": t["strand"],
            "unit": t["unit"],
            "title": t["unitName"],
            "source": "EDB 課程指引",
            "topicCount": 1,
        }
    standards = {
        "edition": "hk-edb",
        "label": "香港教育局課程指引的學習單元",
        "note": "以小學／初中／高中數學學習內容、科學（中一至中三）與物理課程及評估指引、"
                "英國語文課程指引為依據；英語沒有單元，按學習階段與學習範疇對齊。",
        "items": sorted(std_items.values(), key=lambda x: (x["subject"], x["keyStage"], x["unit"])),
    }

    # ---- 给界面用的层级结构 ----
    structure = []
    for subject in ("math", "english", "physics"):
        subj_topics = [t for t in out_topics if t["subject"] == subject]
        stages = []
        for stage, meta in STAGES.items():
            st = [t for t in subj_topics if t["stage"] == stage]
            if not st:
                continue
            strands = OrderedDict()
            for t in st:
                strands.setdefault(t["strand"], OrderedDict())
                strands[t["strand"]].setdefault(t["unit"], dict(
                    unit=t["unit"], name=t["unitName"], count=0))
                strands[t["strand"]][t["unit"]]["count"] += 1
            stages.append({
                "stage": stage,
                "label": meta["label"],
                "keyStage": meta["keyStage"],
                "band": meta["band"],
                "count": len(st),
                "strands": [dict(strand=s, units=list(u.values())) for s, u in strands.items()],
            })
        structure.append(dict(subject=subject, count=len(subj_topics), stages=stages))

    print("知识点：%d → %d（删掉 %d）" % (len(topics), len(out_topics), len(dropped)))
    print("题目：  %d → %d" % (len(questions), len(out_questions)))
    print("先修边：%d → %d（另有 %d 条先修比本知识点更晚，按香港顺序不成立，已去掉）"
          % (len(deps), len(out_deps), len(dropped_edges)))
    for e in dropped_edges:
        print("    - %s ← %s（%s ← %s）"
              % (e["topicId"], e["prerequisiteId"],
                 grade_of[e["topicId"]], grade_of[e["prerequisiteId"]]))
    print("学习单元：%d 个" % len(standards["items"]))
    print("\n各学科：")
    for s in structure:
        print("  %-8s %4d 点" % (s["subject"], s["count"]))
        for st in s["stages"]:
            print("      %-8s %4d" % (st["label"], st["count"]))
    print("\n各阶段合计：")
    for k, v in sorted(Counter(t["stageLabel"] for t in out_topics).items()):
        print("  %-10s %4d" % (k, v))
    print("\n删掉的 %d 个（前 12 个）：" % len(dropped))
    for tid, name, why in dropped[:12]:
        print("  %-9s %-16s %s" % (tid, name[:16], why[:40]))

    if DRY:
        print("\n--dry-run：没有写文件")
        return

    save(DATA / "topics.json", out_topics)
    save(DATA / "questions.json", out_questions)
    save(DATA / "dependencies.json", out_deps)
    save(DATA / "id-aliases.json", out_alias_doc)
    save(DATA / "edb-standards.json", standards)
    save(DATA / "hk-structure.json", dict(subjects=structure))
    # 内地课标文件不再使用
    old = DATA / "cn-curriculum-standards.json"
    if old.exists():
        old.unlink()
        print("\n已删除 data/cn-curriculum-standards.json")
    print("\n已写入 data/{topics,questions,dependencies,id-aliases,edb-standards,hk-structure}.json")


if __name__ == "__main__":
    main()
