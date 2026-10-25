#!/usr/bin/env python3
"""生成 assets/i18n-hant.js 的简→繁映射表。

用法（需要 opencc-python-reimplemented）：
    python3 scripts/build_i18n_hant.py

做法：把仓库里所有会显示给用户的中文（data/*.json、*.html、*.js 的字符串）
收集起来，用 OpenCC(s2tw) 作为标准答案，然后

1. 逐字映射：单字转换结果只有一个字时收进 charMap；
2. 词组覆盖：对语料里出现过的 2–4 字片段，如果 OpenCC 整段转换的结果
   和「逐字映射」的结果不同，就把这段收进 phraseMap（运行时优先按最长匹配）。

这样浏览器里只带两张小表，就能对全部语料复现 OpenCC 的结果，
而不用把 8 MB 的数据文件预先转换一遍。
"""
import json
import re
import sys
from pathlib import Path

from opencc import OpenCC

ROOT = Path(__file__).resolve().parent.parent
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
NGRAM_MIN, NGRAM_MAX = 2, 6


def corpus_texts():
    """收集语料：JSON 里的字符串值、HTML 文本、JS 字符串字面量。"""
    for p in sorted(ROOT.glob("data/**/*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # 语料文件损坏时不应该静默跳过
            print(f"skip {p}: {exc}", file=sys.stderr)
            continue
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, str):
                yield cur
            elif isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)

    for pattern in ("*.html", "**/*.html", "*.js", "**/*.js"):
        for p in ROOT.glob(pattern):
            if ".git" in p.parts or "vendor" in p.parts:
                continue
            if p.name.startswith("i18n-hant"):
                continue
            yield p.read_text(encoding="utf-8")


def main():
    cc = OpenCC("s2tw")
    chars = set()
    grams = {}

    for text in corpus_texts():
        if not CJK.search(text):
            continue
        chars.update(CJK.findall(text))
        # 只在汉字串上取 n-gram，避免把标点带进表里
        for run in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+", text):
            for n in range(NGRAM_MIN, NGRAM_MAX + 1):
                for i in range(len(run) - n + 1):
                    grams.setdefault(run[i:i + n], None)

    char_map = {}
    for ch in sorted(chars):
        out = cc.convert(ch)
        if out != ch and len(out) == 1:
            char_map[ch] = out

    def apply_chars(s):
        return "".join(char_map.get(c, c) for c in s)

    # 从短到长增量收录：已经被更短的词条解释掉的片段不再重复存，
    # 表能小一大截，转换结果不变。
    phrase_map = {}

    def apply_table(s):
        out = []
        i = 0
        while i < len(s):
            for n in range(NGRAM_MAX, NGRAM_MIN - 1, -1):
                piece = s[i:i + n]
                if len(piece) == n and piece in phrase_map:
                    out.append(phrase_map[piece])
                    i += n
                    break
            else:
                out.append(apply_chars(s[i]))
                i += 1
        return "".join(out)

    for gram in sorted(grams, key=lambda g: (len(g), g)):
        expected = cc.convert(gram)
        # 逐字映射已经把这段转对了就跳过；否则收录（包括 X→X 这种
        # 「别按逐字表转」的保护条目，例如「干涉」不能被转成「幹涉」）。
        if expected == apply_table(gram):
            continue
        phrase_map[gram] = expected

    payload = json.dumps(
        {
            "v": 1,
            "source": "OpenCC s2tw",
            "chars": "".join(f"{k}{v}" for k, v in char_map.items()),
            "phrases": phrase_map,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    out_path = ROOT / "assets" / "i18n-hant.js"
    out_path.write_text(
        "/* 自动生成，请勿手改：python3 scripts/build_i18n_hant.py */\n"
        "window.__I18N_HANT__ = " + payload + ";\n",
        encoding="utf-8",
    )
    print(f"chars={len(char_map)} phrases={len(phrase_map)} bytes={out_path.stat().st_size}")


if __name__ == "__main__":
    main()
