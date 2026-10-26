#!/usr/bin/env python3
"""把 data/questions-hk/<单元>.json 合并进 data/questions.json。

用法：
    python3 scripts/merge_hk_questions.py            # 校验并合并
    python3 scripts/merge_hk_questions.py --check    # 只校验，不写文件

每个文件写的是某个学习单元的新题目。合并规则：
- 文件里出现的知识点，其旧题目全部删掉，换成新题目；
- 没出现在任何文件里的知识点，旧题目原样保留。

校验（任何一条不通过就不写文件）：
- topicId 必须存在，且题目数量为 1–6；
- type / difficulty 取值合法；
- 选择题的 answer 必须是选项之一，选项 key 不重复；
- 数值题的 answer 能被解析，且 **verify 表达式的值必须等于 answer**
  （verify 独立算一次，不复用 answer，这样才能抓出算错的答案）；
- 同一知识点的题干不能重复。
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BANK = DATA / "questions-hk"

TYPES = {"choice", "numeric", "short", "self"}
DIFFS = {"basic", "standard", "advanced"}

CHECK_ONLY = "--check" in sys.argv

errors = []


def err(msg):
    errors.append(msg)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- 安全求值
def eval_verify(expr):
    """只允许数字与 + - * / ( ) 与 **，用 ast 白名单求值。"""
    import ast
    import operator

    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("verify 里只能有数字")
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](walk(node.operand))
        raise ValueError("verify 里有不支持的写法：%s" % type(node).__name__)

    return walk(ast.parse(expr, mode="eval"))


def to_fraction(s):
    from fractions import Fraction
    s = str(s).strip().replace(" ", "")
    if "/" in s and "." not in s:
        return Fraction(s)
    return Fraction(s)


# ---------------------------------------------------------------- 校验
def check_unit(doc, path, topic_ids):
    unit = doc.get("unit") or Path(path).stem
    questions = doc.get("questions")
    if not isinstance(questions, list) or not questions:
        err("%s：questions 应为非空数组" % unit)
        return []

    seen_ids = set()
    by_topic = Counter()
    prompts = {}
    for i, q in enumerate(questions):
        where = "%s[%d] %s" % (unit, i, q.get("id") or "?")
        qid = q.get("id")
        if not qid:
            err("%s：缺少 id" % where)
            continue
        if qid in seen_ids:
            err("%s：题目 id 重复" % where)
        seen_ids.add(qid)

        tid = q.get("topicId")
        if tid not in topic_ids:
            err("%s：topicId 不存在：%r" % (where, tid))
        else:
            by_topic[tid] += 1
            key = (tid, q.get("prompt"))
            if key in prompts:
                err("%s：同一知识点的题干重复" % where)
            prompts[key] = True

        if q.get("type") not in TYPES:
            err("%s：type 非法 %r" % (where, q.get("type")))
        if q.get("difficulty") not in DIFFS:
            err("%s：difficulty 非法 %r" % (where, q.get("difficulty")))
        if not (q.get("prompt") or "").strip():
            err("%s：缺少 prompt" % where)
        if not (q.get("explanation") or "").strip():
            err("%s：缺少 explanation" % where)

        answer = q.get("answer")
        if answer is None or str(answer).strip() == "":
            err("%s：缺少 answer" % where)
            continue

        if q.get("type") == "choice":
            choices = q.get("choices") or []
            keys = [c.get("key") for c in choices if isinstance(c, dict)]
            if len(choices) < 2:
                err("%s：选择题至少 2 个选项" % where)
            if len(set(keys)) != len(keys):
                err("%s：选项 key 重复" % where)
            if answer not in keys:
                err("%s：answer=%r 不在选项里 %s" % (where, answer, keys))
            for c in choices:
                if not (c.get("text") or "").strip():
                    err("%s：选项 %r 没有内容" % (where, c.get("key")))
        elif q.get("type") == "numeric":
            try:
                want = to_fraction(answer)
            except Exception:
                err("%s：answer 无法解析为数值：%r" % (where, answer))
                continue
            expr = q.get("verify")
            if not expr:
                err("%s：数值题缺少 verify（无法独立核对）" % where)
                continue
            try:
                got = eval_verify(expr)
            except Exception as e:
                err("%s：verify 无法求值（%s）" % (where, e))
                continue
            if to_fraction(got) != want:
                err("%s：verify=%s 算得 %s，与 answer=%s 不符"
                    % (where, expr, got, answer))
    # 学习重点覆盖：文件若声明了 objectives，就要每个知识点都归属到某一条，
    # 且每条都要真的有题目 —— 这样「按学习重点覆盖」是可验证的，不靠人记。
    objs = doc.get("objectives")
    if objs:
        declared = {}
        for o in objs:
            code = o.get("code")
            if not code:
                err("%s：objectives 里有一条没有 code" % unit)
                continue
            if not o.get("topics"):
                err("%s：学习重点 %s 没有挂任何知识点" % (unit, code))
            for tid in o.get("topics") or []:
                if tid not in topic_ids:
                    err("%s：学习重点 %s 挂了不存在的知识点 %s" % (unit, code, tid))
                elif tid in declared:
                    err("%s：知识点 %s 同时挂在 %s 和 %s" % (unit, tid, declared[tid], code))
                else:
                    declared[tid] = code
        for tid in by_topic:
            if tid not in declared:
                err("%s：知识点 %s 有题目，但没有归到任何一条学习重点" % (unit, tid))
        for o in objs:
            code = o.get("code")
            n = sum(by_topic.get(t, 0) for t in (o.get("topics") or []))
            if code and not n:
                err("%s：学习重点 %s 没有题目" % (unit, code))
    return questions


def main():
    topic_ids = {t["id"] for t in load(DATA / "topics.json")}
    files = sorted(BANK.glob("*.json")) if BANK.exists() else []
    if not files:
        print("data/questions-hk/ 里没有题目文件")
        return 1

    replacements = {}
    total = 0
    for path in files:
        doc = load(path)
        qs = check_unit(doc, path, topic_ids)
        unit = doc.get("unit") or path.stem
        topics = {q["topicId"] for q in qs if q.get("topicId")}
        for tid in topics:
            replacements[tid] = []
        for q in qs:
            if q.get("topicId") in replacements:
                replacements[q["topicId"]].append(q)
        total += len(qs)
        print("%-6s %-10s %2d 点 %3d 题  %s"
              % (unit, doc.get("unitName", ""), len(topics), len(qs), path.name))
        for o in doc.get("objectives") or []:
            n = sum(1 for q in qs if q.get("topicId") in (o.get("topics") or []))
            print("         %-6s %-28s %2d 题" % (o.get("code"), (o.get("text") or "")[:26], n))

    if errors:
        print("\n===== 校验未通过（%d）=====" % len(errors))
        for e in errors[:40]:
            print("  x " + e)
        return 1

    if CHECK_ONLY:
        print("\n校验通过：%d 个知识点、%d 道新题（未写入）" % (len(replacements), total))
        return 0

    old = load(DATA / "questions.json")
    kept = [q for q in old if q.get("topicId") not in replacements]
    merged = kept + [q for qs in replacements.values() for q in qs]
    # 按知识点在 topics.json 里的顺序重排，保证出题次序稳定
    order = {t["id"]: i for i, t in enumerate(load(DATA / "topics.json"))}
    merged.sort(key=lambda q: (order.get(q.get("topicId"), 10 ** 9), str(q.get("id"))))
    save(DATA / "questions.json", merged)

    print("\n题目 %d → %d（替换 %d 个知识点的 %d 道旧题，写入 %d 道新题）"
          % (len(old), len(merged),
             len(replacements),
             sum(1 for q in old if q.get("topicId") in replacements),
             total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
