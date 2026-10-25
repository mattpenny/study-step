#!/usr/bin/env python3
"""从 EDB 数学课程文件里抽出「学习单元」，写到 docs/hk-edb/math-learning-units.json。

用法：
    python3 scripts/extract_hk_math_units.py     # 需要先跑 scripts/fetch_hk_edb.py

只读本地 PDF，不联网。抽的是：学段、范畴、单元编号、单元名称（繁体），
以及该单元的学习重点全文（给 scripts/build_hk_math_mapping.py 做匹配用）。

用中文版（繁体）小册子：知识点名是中文，对中文单元名匹配更准。
中文版 PDF 的字间带空格（「一 元 二 次 方 程」），先压掉空格再解析。
"""
import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "docs" / "hk-edb" / "pdf"
OUT = ROOT / "docs" / "hk-edb" / "math-learning-units.json"

PRIMARY_STRAND = {"N": "數", "A": "代數", "M": "度量", "S": "圖形與空間", "D": "數據處理"}
OBJECTIVE_CAP = 1200  # 每个单元保留的学习重点字数，够匹配用


def raw_text(name):
    return "\n".join((page.extract_text() or "") for page in PdfReader(str(PDF_DIR / name)).pages)


def flatten(text):
    """压掉 PDF 字间空格，保留换行。"""
    text = re.sub(r"[ \t\u00a0]+", "", text)
    return re.sub(r"\n{2,}", "\n", text)


def tidy(s):
    return re.sub(r"\s+", "", s)


# ------------------------------------------------------------------ 小学
def primary_units():
    text = raw_text("math-primary-content-2017-tc.pdf")
    # 单元编号单独一行，名称在下一行
    marks = [(m.start(), m.group(1), m.end())
             for m in re.finditer(r"(?<![A-Za-z0-9])([1-6][NAMSD]\d)\s*\n", text)]
    units, seen = [], set()
    for idx, (pos, code, end) in enumerate(marks):
        if code in seen:
            continue
        name_match = re.match(r"\s*([^\n]{1,40})\n", text[end:])
        if not name_match:
            continue
        name = tidy(name_match.group(1))
        # 排除注释里的交叉引用（如「貨幣(二)」之前。）
        if not name or any(ch in name for ch in "「」《》。："):
            continue
        seen.add(code)
        stop = marks[idx + 1][0] if idx + 1 < len(marks) else len(text)
        units.append({
            "code": code,
            "name": name,
            "strand": PRIMARY_STRAND[code[1]],
            "year": int(code[0]),
            "keyStage": "KS1" if int(code[0]) <= 3 else "KS2",
            "objectives": tidy(text[end:stop])[:OBJECTIVE_CAP],
        })
    return sorted(units, key=lambda u: (u["year"], u["code"]))


# ------------------------------------------------------------------ 初中
JS_STRANDS = ["數與代數", "度量、圖形與空間", "數據處理"]


def strand_at(text, pos):
    found = None
    for name in JS_STRANDS:
        for m in re.finditer(re.escape(name) + r"範疇", text[:pos]):
            if found is None or m.start() > found[0]:
                found = (m.start(), name)
    return found[1] if found else "數與代數"


def numbered_units(text, section_label):
    """形如「1.基礎計算1.1...」：单元名到第一个「N.M」学习重点编号为止。"""
    text = flatten(text)
    marks = [(m.start(), int(m.group(1)), m.end(), m.group(2))
             for m in re.finditer(r"(?<![\d.])(\d{1,2})\.([\u4e00-\u9fff（）()、\s]{2,32}?)(?=\s*\d{1,2}\.\d)", text)]
    units, seen = [], set()
    for idx, (pos, number, end, name) in enumerate(marks):
        key = (section_label, number)
        if key in seen:
            continue
        seen.add(key)
        stop = marks[idx + 1][0] if idx + 1 < len(marks) else len(text)
        # 单元名可能跨行折开（「對數函\n數」），也可能把页眉吃进来
        units.append({
            "unit": number,
            "name": tidy(name.split("學習單位")[0]),
            "strand": strand_at(text, pos),
            "section": section_label,
            "objectives": tidy(text[end:stop])[:OBJECTIVE_CAP],
        })
    return sorted(units, key=lambda u: u["unit"])


def junior_units():
    flat = flatten(raw_text("math-js-content-2017-tc.pdf"))
    # 目录里也有章名，所以从 1000 字之后找正文的章标题，末尾用最后一个「第三章流程圖」
    start = flat.find("第二章學習內容", 1000)
    end = flat.rfind("第三章流程圖")
    if start < 0 or end < start:
        raise SystemExit("初中小册子的章节位置变了，检查 math-js-content-2017-tc.pdf")
    return numbered_units(flat[start:end], "初中")


# ------------------------------------------------------------------ 高中
def senior_units():
    text = raw_text("math-ss-content-2017-tc.pdf")
    flat = flatten(text)
    m1 = flat.find("高中數學單元一(微積分與統計)課程的學習內容")
    m2 = flat.find("高中數學單元二(代數與微積分)課程的學習內容")
    flow = flat.find("第三章流程圖")
    if not (0 < m1 < m2):
        raise SystemExit("高中小册子的分段位置变了，检查 math-ss-content-2017-tc.pdf")
    compulsory = flat[flat.find("學習單位學習重點"):m1]
    return {
        "compulsory": numbered_units(compulsory, "必修部分"),
        "m1": numbered_units(flat[m1:m2], "單元一（微積分與統計）"),
        "m2": numbered_units(flat[m2:flow if flow > m2 else len(flat)], "單元二（代數與微積分）"),
    }


def main():
    if not (PDF_DIR / "math-primary-content-2017-tc.pdf").exists():
        raise SystemExit("先运行 python3 scripts/fetch_hk_edb.py 下载 PDF")

    primary = primary_units()
    junior = junior_units()
    senior = senior_units()

    payload = {
        "source": "Supplement to Mathematics Education KLA Curriculum Guide (2017) — Learning Content of Primary / Junior Secondary / Senior Secondary Mathematics（中文版）",
        "note": "单元名称与学习重点由 PDF 文本抽取，个别跨行标题可能被截断，使用前请对照 PDF 抽查。小学单元编号 = 年级 + 范畴首字母 + 序号。",
        "primary": {"strands": ["數", "代數", "度量", "圖形與空間", "數據處理"], "units": primary},
        "junior_secondary": {"strands": JS_STRANDS, "units": junior},
        "senior_secondary": senior,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"primary {len(primary)}  junior {len(junior)}  "
          f"senior compulsory {len(senior['compulsory'])} / M1 {len(senior['m1'])} / M2 {len(senior['m2'])}")
    print(f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
