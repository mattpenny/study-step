#!/usr/bin/env python3
"""校验香港版数据：data/topics.json、dependencies.json、questions.json、edb-standards.json。

用法：python3 scripts/validate.py
全部通过时打印 "VALIDATION PASSED" 并以退出码 0 结束，否则退出码为 1。

这份校验器对应的是香港课程的结构（学习阶段 / 范畴 / 学习单元），
不是原来那套人教版 + 内地课标的规则。检查的内容：

- 知识点：字段齐全、id 唯一且前缀与学科一致、stage 与 keyStage 一致、
  unit 非空、standards 指向 data/edb-standards.json 里存在的学习单元；
- 先修：两端都存在、无自环、无环、先修不晚于本知识点（按学习阶段比较）；
- 题库：id 唯一、topicId 存在、type/difficulty 合法、答案非空、
  选择题的 answer 必须是选项之一、数值题答案可解析、图形与内联 SVG 合法；
- 别名：指向存在的知识点。
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_figures import question_figure_problems  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

TOPICS_PATH = os.path.join(DATA, "topics.json")
DEPS_PATH = os.path.join(DATA, "dependencies.json")
QUESTIONS_PATH = os.path.join(DATA, "questions.json")
STANDARDS_PATH = os.path.join(DATA, "edb-standards.json")
ALIASES_PATH = os.path.join(DATA, "id-aliases.json")

SUBJECT_PREFIX = {"cnm_": "math", "cne_": "english", "cnp_": "physics"}
SUBJECTS = {"math", "english", "physics"}

# 学习阶段 → (keyStage, 排序号)。中一至中三、中四至中六 是阶段，不是年级。
STAGES = {
    "P1": ("KS1", 1), "P2": ("KS1", 2), "P3": ("KS1", 3),
    "P4": ("KS2", 4), "P5": ("KS2", 5), "P6": ("KS2", 6),
    "P1-P3": ("KS1", 1), "P4-P6": ("KS2", 4),
    "S1-S3": ("KS3", 7), "S4-S6": ("KS4", 10),
}
STAGE_LABEL = {
    "P1": "小一", "P2": "小二", "P3": "小三", "P4": "小四", "P5": "小五", "P6": "小六",
    "P1-P3": "小一至小三", "P4-P6": "小四至小六",
    "S1-S3": "中一至中三", "S4-S6": "中四至中六",
}

TYPES = {"conceptual", "procedural", "reasoning", "application", "modeling"}
QUESTION_TYPES = {"choice", "numeric", "short", "self"}
DIFFICULTIES = {"basic", "standard", "advanced"}
STRENGTHS = {"hard", "soft"}
CONFIDENCES = {"exact", "inferred"}

# 各学科的范畴白名单（香港）
STRANDS = {
    "math": {"數", "代數", "數與代數", "度量", "圖形與空間", "度量、圖形與空間", "數據處理"},
    "physics": {"物理"},
    "english": {"Knowledge", "Interpersonal", "Experience"},
}
EN_DOMAINS = {"语音", "词汇", "语法", "日常表达", "读写"}
STD_ID_RE = re.compile(r"^edb-(math|physics|english):[A-Za-z0-9\-]+$")
NUM_RE = re.compile(r"^-?(?:\d+(?:\.\d+)?|\.\d+)(?:/\d+(?:\.\d+)?)?$")

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load(path, required=True):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if required:
            err("文件不存在：%s" % os.path.relpath(path, ROOT))
    except json.JSONDecodeError as e:
        err("JSON 不合法：%s（%s）" % (os.path.relpath(path, ROOT), e))
    return None


def nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def subject_of(tid):
    for prefix, name in SUBJECT_PREFIX.items():
        if str(tid).startswith(prefix):
            return name
    return None


# ---------------------------------------------------------------- 知识点
def check_topics(topics):
    ids = set()
    for i, t in enumerate(topics):
        where = "topics[%d]" % i
        if not isinstance(t, dict):
            err("%s 不是对象" % where)
            continue
        tid = t.get("id")
        if not nonempty_str(tid):
            err("%s 缺少 id" % where)
            continue
        where = tid
        if tid in ids:
            err("%s id 重复" % where)
        ids.add(tid)

        subject = subject_of(tid)
        if subject is None:
            err("%s id 前缀不认识（应为 cnm_ / cne_ / cnp_）" % where)
            continue
        if t.get("subject") != subject:
            err("%s subject 应为 %s，实际 %r" % (where, subject, t.get("subject")))

        for field in ("name", "description", "unit", "unitName", "stage", "keyStage", "strand"):
            if not nonempty_str(t.get(field)):
                err("%s 缺少 %s" % (where, field))

        stage = t.get("stage")
        if stage not in STAGES:
            err("%s stage 取值非法：%r" % (where, stage))
        else:
            want_ks, want_grade = STAGES[stage]
            if t.get("keyStage") != want_ks:
                err("%s stage=%s 应配 keyStage=%s，实际 %r" % (where, stage, want_ks, t.get("keyStage")))
            if t.get("grade") != want_grade:
                err("%s stage=%s 的排序号应为 %d，实际 %r" % (where, stage, want_grade, t.get("grade")))
            if t.get("stageLabel") != STAGE_LABEL[stage]:
                err("%s stageLabel 应为 %s，实际 %r" % (where, STAGE_LABEL[stage], t.get("stageLabel")))

        strand = t.get("strand")
        if strand and strand not in STRANDS[subject]:
            err("%s 范畴不在香港课程里：%r" % (where, strand))

        if subject == "english":
            if t.get("domain") not in EN_DOMAINS:
                err("%s 英语 domain 取值非法：%r" % (where, t.get("domain")))
        elif t.get("domain") != strand:
            err("%s domain 应等于范畴 %r，实际 %r" % (where, strand, t.get("domain")))

        if t.get("type") not in TYPES:
            err("%s type 取值非法：%r" % (where, t.get("type")))

        mc = t.get("mastery_criteria")
        if not isinstance(mc, list) or not mc:
            err("%s mastery_criteria 应为非空数组" % where)

        stds = t.get("standards")
        if not isinstance(stds, list) or not stds:
            err("%s standards 应为非空数组" % where)
        else:
            if len(stds) > 3:
                err("%s standards 最多 3 条" % where)
            for sd in stds:
                if not isinstance(sd, dict) or not nonempty_str(sd.get("id")):
                    err("%s standards 条目缺少 id" % where)
                    continue
                if sd.get("confidence") not in CONFIDENCES:
                    err("%s standards confidence 只能是 exact / inferred" % where)
                m = STD_ID_RE.match(sd["id"])
                if not m:
                    err("%s 学习单元编号格式不对：%s" % (where, sd["id"]))
                elif m.group(1) != subject:
                    err("%s 学习单元 %s 与学科 %s 不匹配" % (where, sd["id"], subject))
    return ids


# ---------------------------------------------------------------- 先修
def check_deps(deps, ids):
    seen = set()
    prereqs = defaultdict(list)
    for i, d in enumerate(deps):
        where = "dependencies[%d]" % i
        if not isinstance(d, dict):
            err("%s 不是对象" % where)
            continue
        tid, pid = d.get("topicId"), d.get("prerequisiteId")
        if tid not in ids:
            err("%s topicId 不存在：%r" % (where, tid))
            continue
        if pid not in ids:
            err("%s prerequisiteId 不存在：%r" % (where, pid))
            continue
        if tid == pid:
            err("%s 先修边自环：%s" % (where, tid))
        key = (tid, pid)
        if key in seen:
            err("%s 重复的先修边：%s <- %s" % (where, tid, pid))
            continue
        seen.add(key)
        if d.get("strength") not in STRENGTHS:
            err("%s strength 只能是 hard / soft" % where)
        prereqs[tid].append(pid)
    return prereqs


def check_cycles(ids, prereqs):
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {i: WHITE for i in ids}
    for start in ids:
        if color[start] != WHITE:
            continue
        stack = [(start, iter(prereqs.get(start, [])))]
        color[start] = GRAY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if color[nxt] == GRAY:
                    err("先修关系里有环：%s -> %s" % (node, nxt))
                    return
                if color[nxt] == WHITE:
                    color[nxt] = GRAY
                    stack.append((nxt, iter(prereqs.get(nxt, []))))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()


def check_order(topics_by_id, prereqs):
    """先修的阶段不能晚于本知识点：小一不能被中四的知识点当先修。"""
    bad = 0
    for tid, plist in prereqs.items():
        t = topics_by_id.get(tid)
        if not t:
            continue
        for pid in plist:
            p = topics_by_id.get(pid)
            if not p:
                continue
            if p.get("grade", 0) > t.get("grade", 0):
                bad += 1
                if bad <= 10:
                    warn("%s（%s）的先修 %s（%s）阶段更晚"
                         % (tid, t.get("stageLabel"), pid, p.get("stageLabel")))
    if bad:
        warn("共有 %d 条先修边的先修阶段晚于本知识点（跨阶段对应，需人工确认）" % bad)


# ---------------------------------------------------------------- 学习单元
def check_standards(std, ids, topics):
    if not std:
        return set()
    items = std.get("items")
    if not isinstance(items, list) or not items:
        err("edb-standards.json 的 items 应为非空数组")
        return set()
    std_ids = set()
    for i, it in enumerate(items):
        where = "edb-standards.items[%d]" % i
        if not isinstance(it, dict) or not nonempty_str(it.get("id")):
            err("%s 缺少 id" % where)
            continue
        sid = it["id"]
        if sid in std_ids:
            err("%s id 重复：%s" % (where, sid))
        std_ids.add(sid)
        if not STD_ID_RE.match(sid):
            err("%s 编号格式不对：%s" % (where, sid))
        for field in ("subject", "title", "strand", "keyStage"):
            if not nonempty_str(it.get(field)):
                err("%s 缺少 %s" % (where, field))

    cited = set()
    for t in topics:
        for sd in t.get("standards") or []:
            sid = sd.get("id")
            cited.add(sid)
            if sid not in std_ids:
                err("%s 引用的学习单元 %s 不在 edb-standards.json 里" % (t.get("id"), sid))
    unused = std_ids - cited
    if unused:
        warn("有 %d 个学习单元没有被任何知识点引用：%s"
             % (len(unused), "、".join(sorted(unused)[:12])))
    return std_ids


# ---------------------------------------------------------------- 题库
def parse_numeric_answer(s):
    if not isinstance(s, str):
        return None
    out = []
    for part in re.split(r"[，,]", s.replace(" ", "")):
        if not NUM_RE.match(part):
            return None
        try:
            out.append(Fraction(part))
        except (ValueError, ZeroDivisionError):
            return None
    return out


def check_questions(questions, topics_by_id):
    ids = set()
    per_topic = Counter()
    for i, q in enumerate(questions):
        where = "questions[%d]" % i
        if not isinstance(q, dict):
            err("%s 不是对象" % where)
            continue
        qid = q.get("id")
        if not nonempty_str(qid):
            err("%s 缺少 id" % where)
            continue
        where = qid
        if qid in ids:
            err("%s 题目 id 重复" % where)
        ids.add(qid)

        tid = q.get("topicId")
        if tid not in topics_by_id:
            err("%s topicId 不存在：%r" % (where, tid))
        else:
            per_topic[tid] += 1

        if q.get("type") not in QUESTION_TYPES:
            err("%s type 取值非法：%r" % (where, q.get("type")))
        if q.get("difficulty") not in DIFFICULTIES:
            err("%s difficulty 取值非法：%r" % (where, q.get("difficulty")))
        if not nonempty_str(q.get("prompt")):
            err("%s 缺少 prompt" % where)
        if not nonempty_str(q.get("answer")):
            err("%s 缺少 answer" % where)

        choices = q.get("choices")
        if q.get("type") == "choice":
            if not isinstance(choices, list) or len(choices) < 2:
                err("%s 选择题至少要有 2 个选项" % where)
            else:
                keys = [c.get("key") for c in choices if isinstance(c, dict)]
                if len(keys) != len(choices):
                    err("%s 选项缺少 key" % where)
                elif len(set(keys)) != len(keys):
                    err("%s 选项 key 重复" % where)
                elif q.get("answer") not in keys:
                    err("%s answer=%r 不在选项里（%s）" % (where, q.get("answer"), "、".join(map(str, keys))))
        elif choices is not None and not isinstance(choices, list):
            err("%s choices 应为数组" % where)

        if q.get("type") == "numeric":
            if parse_numeric_answer(q.get("answer")) is None:
                if not q.get("accept"):
                    err("%s 数值题答案无法解析：%r" % (where, q.get("answer")))

        for problem in question_figure_problems(q):
            err("%s %s" % (where, problem))

    missing = [tid for tid in topics_by_id if not per_topic.get(tid) and not topics_by_id[tid].get("external")]
    if missing:
        warn("%d 个知识点没有题目（前 10 个：%s）" % (len(missing), "、".join(missing[:10])))
    return ids, per_topic


def check_aliases(alias_doc, ids):
    aliases = (alias_doc or {}).get("aliases") or {}
    for key, spec in aliases.items():
        targets = (spec or {}).get("targets") or []
        if not targets:
            err("id-aliases: %s 没有 targets" % key)
        for t in targets:
            if t not in ids:
                err("id-aliases: %s 指向不存在的知识点 %s" % (key, t))


# ---------------------------------------------------------------- 报告
def report(topics, questions, deps, per_topic):
    print("\n===== 数据概况 =====")
    by_subject = Counter(t.get("subject") for t in topics)
    for s in ("math", "english", "physics"):
        n = by_subject.get(s, 0)
        qs = sum(per_topic[t["id"]] for t in topics if t.get("subject") == s)
        print("  %-8s %4d 个知识点 %5d 道题" % (s, n, qs))
    print("  合计     %4d 个知识点 %5d 道题 %d 条先修边" % (len(topics), len(questions), len(deps)))

    print("\n===== 按学习阶段 =====")
    order = sorted(STAGES, key=lambda s: STAGES[s][1])
    counts = Counter(t.get("stage") for t in topics)
    for stage in order:
        if counts.get(stage):
            print("  %-10s %4d" % (STAGE_LABEL[stage], counts[stage]))

    print("\n===== 按范畴 =====")
    for s in ("math", "physics", "english"):
        c = Counter(t.get("strand") for t in topics if t.get("subject") == s)
        if c:
            print("  %s：%s" % (s, "、".join("%s %d" % (k, v) for k, v in c.most_common())))

    units = {(t.get("subject"), t.get("unit")) for t in topics}
    print("\n  学习单元：%d 个" % len(units))
    qcounts = [per_topic[t["id"]] for t in topics if not t.get("external")]
    if qcounts:
        print("  每知识点题数：最少 %d，最多 %d，平均 %.2f"
              % (min(qcounts), max(qcounts), sum(qcounts) / len(qcounts)))


def main():
    topics = load(TOPICS_PATH)
    deps = load(DEPS_PATH)
    questions = load(QUESTIONS_PATH)
    std = load(STANDARDS_PATH, required=False)
    alias_doc = load(ALIASES_PATH, required=False)

    if not isinstance(topics, list):
        err("topics.json 应为数组")
        topics = []
    if not isinstance(deps, list):
        err("dependencies.json 应为数组")
        deps = []
    if not isinstance(questions, list):
        err("questions.json 应为数组")
        questions = []

    ids = check_topics(topics)
    topics_by_id = {t["id"]: t for t in topics if isinstance(t, dict) and nonempty_str(t.get("id"))}

    prereqs = check_deps(deps, ids)
    check_cycles(ids, prereqs)
    check_order(topics_by_id, prereqs)
    check_standards(std, ids, topics)
    _, per_topic = check_questions(questions, topics_by_id)
    check_aliases(alias_doc, ids)

    report(topics, questions, deps, per_topic)

    if warnings:
        print("\n===== 提示（%d）=====" % len(warnings))
        for w in warnings[:30]:
            print("  ! " + w)
        if len(warnings) > 30:
            print("  … 另有 %d 条" % (len(warnings) - 30))

    if errors:
        print("\n===== 错误（%d）=====" % len(errors))
        for e in errors[:60]:
            print("  x " + e)
        if len(errors) > 60:
            print("  … 另有 %d 条" % (len(errors) - 60))
        print("\nVALIDATION FAILED")
        return 1

    print("\nVALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
