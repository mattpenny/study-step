#!/usr/bin/env python3
"""从 EDB 数学学习内容抽出每个学习单元的学习重点清单。

用法：
    python3 scripts/extract_edb_objectives.py

产物：docs/hk-edb/objectives.json

为什么要这一步：`docs/hk-edb/math-learning-units.json` 里的 objectives 是把 PDF 表格压平后的
一段文字，学习重点、时间栏、注释混在一起。写题目要的是「这个单元要考哪几条」，
所以这里把每条学习重点切出来，变成可以逐条覆盖的清单。

两种版式：
- 初中、高中（含 M1/M2）：学习重点编号是「单元号.序号」，例如 11.1、12.3、1.4。
- 小学：编号是「1. 2. 3. …」，时间栏是小数（3.5、8），所以要求编号必须是 1 起连续整数，
  小数时间（3.5）因为后面跟的是数字，不会被当成编号。

抽不出来的会如实留下空清单并计数，不猜。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HK = ROOT / "docs" / "hk-edb"
OUT = HK / "objectives.json"

# 注释里引用别的学习重点时会写成「在學習重點 1.8 中…」，这类要丢掉
REF_TAIL = re.compile(r"^(中|的|至|及|和|或|內|範|所|，|。|、)")
# 学习重点后面紧接的教师注释，从这些词开始截断
NOTE_START = re.compile(r"(學生須|教師應|教師可|須包括|須認識|注[：︰]|例如|可考慮|只限於|不包括)")


def clean(text):
    return re.sub(r"\s+", "", text or "")


def secondary_objectives(text, unit_no):
    """初中/高中：11.1 / 12.3 这种编号。只保留属于本单元的编号，且丢掉引用型的尾巴。"""
    out = []
    seen = set()
    pat = re.compile(r"(?<![\d.])(\d{1,2}\.\d{1,2})([^\d]{2,60})")
    for code, body in pat.findall(text):
        head, _, tail = code.partition(".")
        if int(head) != unit_no:
            continue
        body = body.strip("，。、；： ")
        if not body or REF_TAIL.match(body):
            continue
        if code in seen:
            continue
        seen.add(code)
        cut = NOTE_START.search(body)
        if cut and cut.start() >= 2:
            body = body[:cut.start()]
        code = "%d.%s" % (int(head), tail)
        out.append({"code": code, "text": body[:40]})
    out.sort(key=lambda x: int(x["code"].split(".")[1]))
    return out


def primary_objectives(text):
    """小学：1. 2. 3. 编号，时间栏是小数。要求从 1 开始连续。"""
    out = []
    # 编号后必须不是数字（否则 3.5 这种时间会被误判）
    pat = re.compile(r"(\d{1,2})\.(?=[^\d])([^\d]{2,60})")
    expect = 1
    for num, body in pat.findall(text):
        n = int(num)
        if n != expect:
            # 时间栏紧贴在编号前时（例如「…概念8 2.理解因數…」），正则会把 8 和 2 一起吃掉，
            # 这时退一步只看最后一位
            if int(num[-1]) != expect:
                continue
            n = expect
        body = body.strip("，。、；： ")
        if not body or REF_TAIL.match(body):
            continue
        cut = NOTE_START.search(body)
        if cut and cut.start() >= 2:
            body = body[:cut.start()]
        out.append({"code": "%d." % n, "text": body[:40]})
        expect += 1
    return out


def main():
    doc = json.loads((HK / "math-learning-units.json").read_text(encoding="utf-8"))
    units = []

    def add(unit_key, name, key_stage, section, text, is_primary, unit_no):
        raw = clean(text)
        objs = primary_objectives(raw) if is_primary else secondary_objectives(raw, unit_no)
        units.append({
            "unit": unit_key,
            "name": name,
            "keyStage": key_stage,
            "section": section,
            "objectives": objs,
            "objectiveCount": len(objs),
        })

    for u in doc["primary"]["units"]:
        add(u["code"], u["name"], u.get("keyStage", ""), "小學", u.get("objectives"), True, 0)

    for u in doc["junior_secondary"]["units"]:
        add("S%d" % u["unit"], u["name"], "KS3", "初中", u.get("objectives"), False, u["unit"])

    prefix = {"compulsory": "COM", "m1": "M1", "m2": "M2"}
    for section, lst in doc["senior_secondary"].items():
        for u in lst:
            add("%s%d" % (prefix[section], u["unit"]), u["name"], "KS4",
                section, u.get("objectives"), False, u["unit"])

    total = sum(u["objectiveCount"] for u in units)
    empty = [u for u in units if not u["objectiveCount"]]
    by_ks = {}
    for u in units:
        by_ks.setdefault(u["keyStage"] or "?", []).append(u["objectiveCount"])

    payload = {
        "source": "EDB《數學教育學習領域課程指引》小學、初中、高中數學學習內容的學習重點",
        "note": "每条 = 一条学习重点。小学按 1./2./3. 连续编号抽取，初中高中按单元号.序号抽取；"
                "抽不到的单元 objectives 为空数组，不猜测。",
        "total": total,
        "units": units,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("单元 %d 个，学习重点共 %d 条" % (len(units), total))
    for ks, counts in sorted(by_ks.items()):
        print("  %-5s %3d 个单元 %4d 条（平均 %.1f）"
              % (ks, len(counts), sum(counts), sum(counts) / len(counts)))
    print("抽不到任何学习重点的单元：%d 个" % len(empty))
    for u in empty[:10]:
        print("   - %s %s" % (u["unit"], u["name"]))

    print("\n样例：")
    for key in ("S11", "S12", "S13", "4N3", "COM1"):
        u = next((x for x in units if x["unit"] == key), None)
        if not u:
            continue
        print("  %s %s（%d 条）" % (u["unit"], u["name"], u["objectiveCount"]))
        for o in u["objectives"]:
            print("     %-5s %s" % (o["code"], o["text"]))


if __name__ == "__main__":
    main()
