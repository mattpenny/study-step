#!/usr/bin/env python3
"""从 EDB 数学课程文件里抽出「学习单元」清单，写到 docs/hk-edb/math-learning-units.json。

用法：
    python3 scripts/extract_hk_math_units.py     # 需要先跑 scripts/fetch_hk_edb.py

只读本地 PDF，不联网。抽的是单元编号 + 名称 + 所属领域 + 学段，
供把本站 827 个数学知识点对到香港课程时用。名称来自 PDF 文本抽取，
个别跨行标题可能被截断，用之前请对照 PDF 抽查。
"""
import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "docs" / "hk-edb" / "pdf"
OUT = ROOT / "docs" / "hk-edb" / "math-learning-units.json"

# 小学单元编号：学段(1-6) + 领域(N/A/M/S/D) + 序号
PRIMARY_CODE = re.compile(r"(?<![A-Za-z0-9])([1-6])([NAMSD])(\d)\s+([A-Z][^\n]{2,70})")
STRAND = {"N": "Number", "A": "Algebra", "M": "Measures", "S": "Shape and Space", "D": "Data Handling"}


def text_of(name):
    reader = PdfReader(str(PDF_DIR / name))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def clean(s):
    return re.sub(r"\s+", " ", s).strip(" .·")


def primary_units(text):
    """单元名可能折行，先按编号抓，再用「学习目标序号」把名字截断到正确长度。"""
    units = {}
    for m in PRIMARY_CODE.finditer(text):
        code, name = f"{m.group(1)}{m.group(2)}{m.group(3)}", clean(m.group(4))
        # 名字里若混进了后面的学习目标文字，截掉
        name = re.split(r"\s+\d+\.\s", name)[0]
        # 折行导致的半截名字：接到下一行开头，直到遇到数字或句点
        if re.search(r"(and|or|of|the|in|with|to)$", name, re.I):
            tail = text[m.end():m.end() + 80]
            extra = re.match(r"\s*\n?\s*([a-z][^\n]{0,60})", tail)
            if extra:
                name = clean(name + " " + extra.group(1))
        name = re.split(r"\s+\d+\.\s", name)[0]
        if code not in units and len(name) > 2:
            units[code] = name
    return units


def js_units(text):
    """初中：单元形如「1. Basic computation」，学习目标形如 1.1；领域按「X Strand」标题的位置判断。"""
    marks = [(m.start(), m.group(1)) for m in re.finditer(
        r"(Number and Algebra|Measures, Shape and Space|Data Handling)\s+Strand", text)]
    pattern = re.compile(r"(?<![.\d])(\d{1,2})\.\s+([A-Z0-9][^\n]{0,70}?(?:\n[a-z][^\n]{0,50})?)\s+\d+\.\d+\s")
    units = {}
    for m in pattern.finditer(text):
        number = int(m.group(1))
        name = clean(m.group(2))
        strand = None
        for pos, label in marks:  # 取该单元之前最近的一个领域标题
            if pos < m.start():
                strand = label
        # 按阅读顺序取第一次出现的标题（单元本身是顺序排列的），
        # 后面的同号匹配多是学习目标编号，不能覆盖
        units.setdefault(number, {"unit": number, "name": name, "strand": strand or "Number and Algebra"})
    return [units[k] for k in sorted(units)]


def main():
    if not (PDF_DIR / "math-primary-content-2017.pdf").exists():
        raise SystemExit("先运行 python3 scripts/fetch_hk_edb.py 下载 PDF")

    primary_text = text_of("math-primary-content-2017.pdf")
    js_text = text_of("math-js-content-2017.pdf")

    prim = primary_units(primary_text)
    primary = [
        {"code": code, "name": name, "strand": STRAND[code[1]], "year": int(code[0])}
        for code, name in sorted(prim.items())
    ]
    js = js_units(js_text)

    payload = {
        "source": "Supplement to Mathematics Education KLA Curriculum Guide (2017) - Learning Content of Primary / Junior Secondary Mathematics",
        "note": "单元名由 PDF 文本抽取，跨行标题可能被截断，使用前请对照 PDF 抽查。小学编号 = 年级+领域首字母+序号；初中按领域分组。",
        "primary": {
            "strands": ["Number", "Algebra", "Measures", "Shape and Space", "Data Handling"],
            "units": primary,
        },
        "junior_secondary": {
            "strands": ["Number and Algebra", "Measures, Shape and Space", "Data Handling", "Further Learning Unit"],
            "units": js,
        },
        "senior_secondary": {
            "note": "高中分必修部分 + 延伸单元一（微积分与统计）+ 延伸单元二（代数与微积分），见 math-ca-guide-2017 与 math-explanatory-cp / m1 / m2。",
            "strands": ["Compulsory Part", "Module 1", "Module 2"],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"primary units: {len(primary)}  junior secondary units: {len(js)}  -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
