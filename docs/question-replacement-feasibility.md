# Replacing all maths questions — feasibility assessment

**Question:** can we throw away the 3,214 maths questions and write new ones aligned to the
EDB curriculum, sourcing questions from the web?

**Short answer:** writing new ones is feasible. **Scraping existing ones is not** — the two
sources that look promising (HKEAA past papers, publisher question banks) are both
licence-gated, and neither may be republished on a public site. Below is the evidence, the
real constraints I found, and a proposed pilot.

---

## 1. What cannot be done

### 1.1 HKDSE past papers (HKEAA)

This is the obvious source and it is **closed**. From HKEAA's own licence page:

> Schools should not, without the HKEAA's prior written approval, use or copy (including
> reproducing or storing in any medium by electronic means) HKEAA's past question papers
> … Although schools have special rights … to copy copyright materials in the course of
> instruction, such rights **do not apply** to copying HKEAA's past … question papers.

The licence is per-school and paid: **HK$5,490** for up to 75% of HKEAA's works, or
**HK$6,955** for 95%, for the 2026/27 year, expiring 31 August 2027. It covers use *in a
school*, not publication in a web app. So past papers are out unless Study Step becomes a
licensed school product with the school holding the licence.

### 1.2 Publisher question banks

朗文 / 牛津 / 培生 / 現代 / 教圖 all publish unit-aligned exercise banks. All copyright,
all behind a school login or a paid platform. Not usable.

### 1.3 "Free" question sites

Sites like `orhk.net` (claims a free HK primary maths bank, ~135 questions per lesson) or
the various 練習 PDFs floating around have **no stated licence**. Copying them into a
product is the same legal exposure as copying a textbook, with none of the quality
assurance. I would not do it.

**Conclusion:** there is no legitimate bulk source of EDB-aligned questions to import.
Any replacement has to be authored.

---

## 2. What can be done

We already hold the strongest asset needed to author them: **the EDB learning content itself**.

| Asset | Where | State |
|---|---|---|
| 115 maths learning units with codes (`1N1`, `S11`, `COM1`…) | `data/edb-standards.json` | clean |
| EDB 學習重點 text per unit | `docs/hk-edb/math-learning-units.json` | present but **dirty** (see §4.1) |
| Topic → unit mapping with confidence | `docs/hk-edb/hk-edb-math.json` | done |
| Question schema built for auto-marking | `data/questions.json` | works (`verify`, `choices`, `accept`) |

So the work is: **write questions against each unit's 學習重點**, in HK terminology, and
verify the answers mechanically. That is a content-authoring job, not a scraping job.

Note that competitors do exactly this — Dsetopia states openly: *"We don't rewrite past
papers. Every question is written from a syllabus objective, then generated."* That is also
the approach least likely to infringe.

---

## 3. Scale

| | |
|---|---:|
| Maths topics | 768 |
| Maths questions today | 3,214 (4.18 per topic) |
| Maths learning units | 115 (median 5 topics per unit) |

How many questions are actually needed? From `diagnose/engine.js`: a topic is asked at most
twice (first attempt, then an easier/equal one). So:

| Target | Questions | Effect |
|---|---:|---|
| Minimum the engine can use | 1,536 (2/topic) | works, but only two difficulty points |
| **Parity with today** | **~3,072 (4/topic)** | same behaviour as now |
| Ideal | ~4,600 (6/topic) | two per difficulty band (basic/standard/advanced) |

**Recommendation: 4 per topic, 3,072 questions**, written unit by unit — 115 batches of
roughly 20 questions each.

---

## 4. Four constraints that will shape the work

### 4.1 The EDB objective text needs cleaning first

The 學習重點 are in the PDFs and extracted, but the extraction flattened a table: the
objective, its time allocation and the footnote all run together, and some units bleed into
the next one. Real example (`1S3 方向和位置(一)`):

> 方向和位置(一)1.認識從觀測者的角度…描述物件的相對位置**3.5**只限於以學生作為觀測者。
> 進階學習單位**1F1**探索與研究…

Here `3.5` is the time allocation and the text after it belongs to the next unit. Compare a
clean one (`11 多項式`): `11.1 理解多項式的概念`, `11.2 進行多項式的加、減、乘…`,
`11.3 因式分解多項式…` — perfectly usable.

So step 1 is a cleaning pass to split 學習重點 / 時間 / 註釋 and respect unit boundaries.
Roughly half the units look clean already; the primary ones are worst. **This is a
prerequisite, and it is a few hours of parsing work, not a rewrite.**

### 4.2 HK terminology differs from what the topics are called

The unit names are HK but the topic names underneath are still mainland wording:

| Topic names contain | Count | HK usage |
|---|---:|---|
| 勾股定理 | 6 | **畢氏定理** |
| 整式 | 4 | **多項式** |
| 锐角三角函数 | 1 | **三角比** |

Note the giveaway: unit `S25` is named **畢氏定理**, and all six topics under it are called
**勾股定理**. Terms that differ only by character form (函数→函數, 众数→眾數) are already
handled by the 繁體 conversion table; the eleven above are **different words** and need
renaming. If questions say 勾股定理 while the unit says 畢氏定理, students will notice
immediately.

### 4.3 "Different classes" — EDB does not assign years to S1–S3

You asked for questions per class. For **P1–P6** that is well defined: the unit code
carries the year (`4N3` = Primary 4).

For **S1–S3** and **S4–S6**, EDB deliberately does **not** say which unit is taught in which
year — schools sequence them. So I can only target *stages* (中一至中三), unless you give me
your school's 教學進度表 / scheme of work, in which case I can label each unit with the form.

### 4.4 Not everything can be auto-marked

The engine grades numerically. For algebra that forces a choice:

| Question form | Auto-marked? | Example |
|---|---|---|
| `numeric` with `verify` | **yes** | 化簡後 x 的係數是多少？ → `3-2` |
| `choice` with expression options | **yes** | 展開 (x+3)(x−5) → A/B/C/D |
| `short` free-form expression | **no** — self-marked | 化簡 3x+5y−2x+7y |

So for algebra-heavy units, questions should be written as "ask for a coefficient / a
specific value / pick the right expansion" rather than "show the simplified expression".
That is a real design constraint on the authoring, and it is why a naive "write 4 questions
per topic" produces lots of unmarkable items.

---

## 5. What a question would look like

Three samples written against `S11 多項式`, in HK terminology, using the existing schema:

```jsonc
// cnm_034 合併同類項 — auto-marked numeric
{ "type": "numeric", "difficulty": "basic",
  "prompt": "化簡 3x + 5y − 2x + 7y 後，x 的係數是多少？",
  "answer": "1", "verify": "3-2",
  "explanation": "3x − 2x = x，所以 x 的係數是 1；y 的部分合共 12y。" }

// cnm_146 多項式乘多項式 — auto-marked choice
{ "type": "choice", "difficulty": "standard",
  "prompt": "展開 (x + 3)(x − 5)。",
  "choices": [{ "key": "A", "text": "x² − 2x − 15" }, { "key": "B", "text": "x² + 2x − 15" },
              { "key": "C", "text": "x² − 15" },     { "key": "D", "text": "x² − 2x + 15" }],
  "answer": "A",
  "explanation": "x² − 5x + 3x − 15 = x² − 2x − 15。" }

// cnm_150 因式分解的概念 — auto-marked numeric
{ "type": "numeric", "difficulty": "standard",
  "prompt": "因式分解 x² + 7x + 12 = (x + a)(x + b)，其中 a < b。求 b。",
  "answer": "4", "verify": "4",
  "explanation": "12 = 3 × 4 且 3 + 4 = 7，所以 x² + 7x + 12 = (x + 3)(x + 4)，b = 4。" }
```

Every one of these can be checked by machine: `verify` recomputes the number, and for choice
questions the answer must be one of the option keys (the validator already enforces this).

---

## 6. Quality control

What I can guarantee mechanically:

- `verify` expressions recomputed independently of `answer` — catches arithmetic slips
- choice answers must exist in the option list; options must have unique keys
- no duplicate prompts within a topic
- terminology lint: flag any question containing 勾股定理 / 整式 / 锐角三角函数 etc.
- every topic covered, difficulty spread present

What I **cannot** guarantee: pedagogical appropriateness, whether a distractor is
"plausible but wrong", whether the reading level suits the year, whether the item is
actually testing the 學習重點. **That needs a teacher.** The upstream README admits its own
bank is "AI-generated, never reviewed by a teacher" — I would rather not repeat that claim
silently for a new bank.

---

## 7. Proposed path

1. **Clean the 學習重點** (parse out 時間/註釋, fix unit bleed) — prerequisite for everything.
2. **Terminology pass**: rename the ~11 topics to HK wording, add a lint rule so it can't regress.
3. **Pilot one unit end-to-end** — `S11 多項式`, 26 topics, ~104 questions. Ship it, look at it, judge the quality before committing to 115 units.
4. **Batch the rest** unit by unit, primary first (P1–P6 is where the year mapping is unambiguous), then 中一至中三, then 中四至中六.
5. Keep the old questions in git, not in the app, until each unit's replacement passes review.

---

## 8. Decisions I need from you

1. **4 per topic (3,072) or 2 per topic (1,536)** to start? The engine works at 2, but the
   second question may be the only fallback.
2. **Do you have a scheme of work** for S1–S3, so units can be labelled by form? Otherwise
   they stay stage-level.
3. **Who reviews?** If nobody, I can still ship machine-verified questions, but the app
   should say plainly that they are unreviewed — the same disclaimer the current bank needs.
4. **Rename the mainland topic names?** 勾股定理 → 畢氏定理 etc. Cheap, and probably wanted
   regardless of the question rewrite.
5. **Start with the pilot unit now?** `S11` is a good first one — clean objectives, 26
   topics, self-contained.
