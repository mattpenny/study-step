#!/usr/bin/env python3
"""下载香港教育局（EDB）课程文件，并生成 docs/hk-edb/syllabus-index.json。

用法：
    python3 scripts/fetch_hk_edb.py            # 下载缺失的文件并刷新索引
    python3 scripts/fetch_hk_edb.py --check    # 只检查链接是否还有效，不下载

DOCS 里是人工核对过的清单：科目、标题、年份、适用学段、官方 PDF 地址。
地址会随教育局改版失效，失效时脚本会在输出里标 FAIL，改这一处即可。

PDF 只放在本地（docs/hk-edb/pdf/，已 gitignore），不进仓库：
这些是香港政府的版权文件，仓库里只保留清单和链接。
"""
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "hk-edb"
PDF_DIR = OUT_DIR / "pdf"
BASE = "https://www.edb.gov.hk"

# subject: math / chinese / english / physics；stages 用 HK 说法
DOCS = [
    # ---------------- 數學 Mathematics ----------------
    dict(file="math-klacg-2017", subject="math", lang="en", year=2017,
         title="Mathematics Education Key Learning Area Curriculum Guide (Primary 1 - Secondary 6)",
         title_zh="數學教育學習領域課程指引（小一至中六）", stages="P1-S6", role="kla-guide",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/ME_KLACG_eng_2017_12_08.pdf"),
    dict(file="math-primary-content-2017", subject="math", lang="en", year=2017,
         title="Supplement to ME KLA Curriculum Guide: Learning Content of Primary Mathematics",
         title_zh="數學教育學習領域課程指引補充文件：小學數學學習內容", stages="P1-P6", role="content",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/pmc2017_e.pdf"),
    dict(file="math-primary-explanatory-ks1-2018", subject="math", lang="en", year=2018,
         title="Explanatory Notes to Primary Mathematics Curriculum - Key Stage 1",
         title_zh="小學數學課程闡釋（第一學習階段）", stages="P1-P3", role="explanatory",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/EN_KS1_e.pdf"),
    dict(file="math-primary-explanatory-ks2-2020", subject="math", lang="en", year=2020,
         title="Explanatory Notes to Primary Mathematics Curriculum - Key Stage 2",
         title_zh="小學數學課程闡釋（第二學習階段）", stages="P4-P6", role="explanatory",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/EN_KS2_e.pdf"),
    dict(file="math-js-content-2017", subject="math", lang="en", year=2017,
         title="Supplement to ME KLA Curriculum Guide: Learning Content of Junior Secondary Mathematics",
         title_zh="數學教育學習領域課程指引補充文件：初中數學學習內容", stages="S1-S3", role="content",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/jsmc2017_e.pdf"),
    dict(file="math-js-explanatory-ks3-2020", subject="math", lang="en", year=2020,
         title="Explanatory Notes to Junior Secondary Mathematics Curriculum",
         title_zh="初中數學課程闡釋（第三學習階段）", stages="S1-S3", role="explanatory",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/EN_KS3_e.pdf"),
    dict(file="math-ss-content-2017", subject="math", lang="en", year=2017,
         title="Supplement to ME KLA Curriculum Guide: Learning Content of Senior Secondary Mathematics",
         title_zh="數學教育學習領域課程指引補充文件：高中數學學習內容", stages="S4-S6", role="content",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/ssmc2017_e.pdf"),
    dict(file="math-ca-guide-2017", subject="math", lang="en", year=2017,
         title="Mathematics Curriculum and Assessment Guide (Secondary 4 - 6)",
         title_zh="數學課程及評估指引（中四至中六）", stages="S4-S6", role="ca-guide",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/CA_2017_e.pdf"),
    dict(file="math-explanatory-cp", subject="math", lang="en", year=2017,
         title="Explanatory Notes to the Compulsory Part of Senior Secondary Mathematics",
         title_zh="高中數學必修部分闡釋", stages="S4-S6", role="explanatory",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/EN_CP_e.pdf"),
    dict(file="math-explanatory-m1", subject="math", lang="en", year=2017,
         title="Explanatory Notes to Mathematics Module 1 (Calculus and Statistics)",
         title_zh="數學延伸部分單元一（微積分與統計）闡釋", stages="S4-S6", role="explanatory",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/EN_M1_e.pdf"),
    dict(file="math-explanatory-m2", subject="math", lang="en", year=2017,
         title="Explanatory Notes to Mathematics Module 2 (Algebra and Calculus)",
         title_zh="數學延伸部分單元二（代數與微積分）闡釋", stages="S4-S6", role="explanatory",
         url=BASE + "/attachment/en/curriculum-development/kla/ma/curr/EN_M2_e.pdf"),

    # 中文版（繁体）——對照時用中文單元名更直接
    dict(file="math-primary-content-2017-tc", subject="math", lang="tc", year=2017,
         title="Supplement to ME KLA Curriculum Guide: Learning Content of Primary Mathematics (Chinese)",
         title_zh="數學教育學習領域課程指引補充文件：小學數學學習內容（中文版）", stages="P1-P6", role="content",
         url=BASE + "/attachment/tc/curriculum-development/kla/ma/curr/pmc2017_tc.pdf"),
    dict(file="math-js-content-2017-tc", subject="math", lang="tc", year=2017,
         title="Supplement to ME KLA Curriculum Guide: Learning Content of Junior Secondary Mathematics (Chinese)",
         title_zh="數學教育學習領域課程指引補充文件：初中數學學習內容（中文版）", stages="S1-S3", role="content",
         url=BASE + "/attachment/tc/curriculum-development/kla/ma/curr/jsmc2017_tc.pdf"),
    dict(file="math-ss-content-2017-tc", subject="math", lang="tc", year=2017,
         title="Supplement to ME KLA Curriculum Guide: Learning Content of Senior Secondary Mathematics (Chinese)",
         title_zh="數學教育學習領域課程指引補充文件：高中數學學習內容（中文版）", stages="S4-S6", role="content",
         url=BASE + "/attachment/tc/curriculum-development/kla/ma/curr/ssmc2017_tc.pdf"),
    dict(file="math-ca-guide-2017-tc", subject="math", lang="tc", year=2017,
         title="Mathematics Curriculum and Assessment Guide (Secondary 4 - 6) (Chinese)",
         title_zh="數學課程及評估指引（中四至中六）（中文版）", stages="S4-S6", role="ca-guide",
         url=BASE + "/attachment/tc/curriculum-development/kla/ma/curr/CA_2017_tc.pdf"),

    # ---------------- 英國語文 English ----------------
    dict(file="eng-klacg-2017", subject="english", lang="en", year=2017,
         title="CDC English Language Education Key Learning Area Curriculum Guide (Primary 1 - Secondary 6)",
         title_zh="英國語文教育學習領域課程指引（小一至中六）", stages="P1-S6", role="kla-guide",
         url=BASE + "/attachment/en/curriculum-development/kla/eng-edu/Curriculum%20Document/ELE%20KLACG_2017.pdf"),
    dict(file="eng-primary-cg-2025", subject="english", lang="en", year=2025,
         title="CDC English Language Curriculum Guide (Primary 1 - 6) 2025",
         title_zh="英國語文課程指引（小一至小六）2025", stages="P1-P6", role="content",
         url=BASE + "/attachment/en/curriculum-development/kla/eng-edu/Curriculum%20Document/Pri_ELCG_Primary_1-6_2025.pdf"),
    dict(file="eng-js-supplement-2018", subject="english", lang="en", year=2018,
         title="Supplement to the ELE KLA Curriculum Guide (Secondary 1 - 3)",
         title_zh="英國語文教育學習領域課程指引補充文件（中一至中三）", stages="S1-S3", role="content",
         url=BASE + "/attachment/en/curriculum-development/kla/eng-edu/Curriculum%20Document/ELE%20JS%20Supplement%202018.pdf"),
    dict(file="eng-ca-guide-2021", subject="english", lang="en", year=2021,
         title="CDC-HKEAA English Language Curriculum and Assessment Guide (Secondary 4 - 6) 2021",
         title_zh="英國語文課程及評估指引（中四至中六）2021", stages="S4-S6", role="ca-guide",
         url=BASE + "/attachment/en/curriculum-development/kla/eng-edu/Curriculum%20Document/English%20Language%20Curriculum%20and%20Assessment%20Guide%20(Secondary%204%20-%206)%20(2021).pdf"),
    dict(file="eng-examples-1-28", subject="english", lang="en", year=2017,
         title="Examples in support of the ELE KLA Curriculum Guide (P1 - S6) 2017",
         title_zh="英國語文教育學習領域課程指引示例", stages="P1-S6", role="examples",
         url=BASE + "/attachment/en/curriculum-development/kla/eng-edu/ELE%20KLACG%202017_Examples%201-28.pdf"),

    # ---------------- 科學 / 物理 Science & Physics ----------------
    dict(file="sci-klacg-2017", subject="physics", lang="en", year=2017,
         title="Science Education Key Learning Area Curriculum Guide (Primary 1 - Secondary 6)",
         title_zh="科學教育學習領域課程指引（小一至中六）", stages="P1-S6", role="kla-guide",
         url=BASE + "/attachment/en/curriculum-development/kla/science-edu/SEKLACG_ENG_2017.pdf"),
    dict(file="sci-primary-cg-2025-chi", subject="physics", lang="tc", year=2025,
         title="Science (Primary 1 - 6) Curriculum Guide 2025 (Chinese only)",
         title_zh="科學（小一至小六）課程指引 2025", stages="P1-P6", role="content",
         url=BASE + "/attachment/tc/curriculum-development/kla/science-edu/pri-sci/PSCG%282025%29.pdf"),
    dict(file="sci-js-supplement-2017", subject="physics", lang="en", year=2017,
         title="Supplement to SE KLA Curriculum Guide: Science (S1 - 3)",
         title_zh="科學教育學習領域課程指引補充文件：科學（中一至中三）", stages="S1-S3", role="content",
         url=BASE + "/attachment/en/curriculum-development/kla/science-edu/Science%28S1-3%29_supp_e_2017.pdf"),
    dict(file="sci-js-framework-2025", subject="physics", lang="en", year=2025,
         title="Supplement to SE KLA Curriculum Guide: Science (S1 - 3) Curriculum Framework 2025",
         title_zh="科學（中一至中三）課程框架 2025", stages="S1-S3", role="content",
         url=BASE + "/attachment/en/curriculum-development/kla/science-edu/JS_Science_Curriculum_Framework_2025_english.pdf"),
    dict(file="phy-ca-guide-2015", subject="physics", lang="en", year=2015,
         title="Physics Curriculum and Assessment Guide (Secondary 4 - 6) 2007, updated Nov 2015",
         title_zh="物理課程及評估指引（中四至中六）", stages="S4-S6", role="ca-guide",
         url=BASE + "/attachment/en/curriculum-development/kla/science-edu/Phy_C_and_A_Guide_updated_e_20151126.pdf"),

    # ---------------- 中國語文 Chinese ----------------
    dict(file="chi-klacg-2017", subject="chinese", lang="tc", year=2017,
         title="Chinese Language Education Key Learning Area Curriculum Guide (Primary 1 - Secondary 6)",
         title_zh="中國語文教育學習領域課程指引（小一至中六）", stages="P1-S6", role="kla-guide",
         url=BASE + "/attachment/tc/curriculum-development/kla/chi-edu/curriculum-documents/CLEKLAG_2017_for_upload_final_R77.pdf"),
    dict(file="chi-primary-cg-2023", subject="chinese", lang="tc", year=2023,
         title="Chinese Language Curriculum Guide (Primary 1 - 6) 2023",
         title_zh="中國語文課程指引（小一至小六）2023", stages="P1-P6", role="content",
         url=BASE + "/attachment/tc/curriculum-development/kla/chi-edu/curriculum-documents/Primary_Chi_Lang_Curr_Guide_2023.pdf"),
    dict(file="chi-primary-lo-2023", subject="chinese", lang="tc", year=2023,
         title="Suggested Learning and Teaching Objectives for Primary Chinese (2023 revision)",
         title_zh="小學中國語文建議學習重點（2023年修訂）", stages="P1-P6", role="content",
         url=BASE + "/attachment/tc/curriculum-development/kla/chi-edu/curriculum-documents/Pri_Chin_Lang_LO_2023.pdf"),
    dict(file="chi-js-cg-2023", subject="chinese", lang="tc", year=2023,
         title="Chinese Language Curriculum Guide (Secondary 1 - 3) 2023",
         title_zh="中國語文課程指引（中一至中三）2023", stages="S1-S3", role="content",
         url=BASE + "/attachment/tc/curriculum-development/kla/chi-edu/curriculum-documents/Junior_Sec_Chi_Lang_Curr_Guide_2023.pdf"),
    dict(file="chi-ca-guide-2021", subject="chinese", lang="tc", year=2021,
         title="Chinese Language Curriculum and Assessment Guide (Secondary 4 - 6) 2021",
         title_zh="中國語文課程及評估指引（中四至中六）2021", stages="S4-S6", role="ca-guide",
         url=BASE + "/attachment/tc/curriculum-development/kla/chi-edu/CHI_LANG_CAGuide_2021.pdf"),
    dict(file="chi-sec-lo-2021", subject="chinese", lang="tc", year=2021,
         title="Suggested Learning and Teaching Objectives for Secondary Chinese",
         title_zh="中學中國語文建議學習重點", stages="S1-S6", role="content",
         url=BASE + "/attachment/tc/curriculum-development/kla/chi-edu/SEC_LO_2021.pdf"),
    dict(file="pth-cg-2017", subject="chinese", lang="tc", year=2017,
         title="Putonghua Curriculum Guide (Primary 1 - Secondary 3) 2017",
         title_zh="普通話科課程指引（小一至中三）2017", stages="P1-S3", role="content",
         url=BASE + "/attachment/tc/curriculum-development/kla/chi-edu/curriculum-documents/PTH_Curriculum_guide_for_upload_final.pdf"),
]


def fetch(url, dest, check_only=False):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as res:
        status = res.status
        data = b"" if check_only else res.read()
    if check_only:
        return status, None, None
    dest.write_bytes(data)
    return status, len(data), hashlib.sha256(data).hexdigest()


def main():
    check_only = "--check" in sys.argv
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    index, failed = [], []

    for doc in DOCS:
        dest = PDF_DIR / (doc["file"] + ".pdf")
        entry = {k: doc[k] for k in ("file", "subject", "lang", "year", "title", "title_zh", "stages", "role", "url")}
        try:
            if check_only or not dest.exists():
                status, size, digest = fetch(doc["url"], dest, check_only)
                entry.update(status=status, bytes=size, sha256=digest)
            else:
                data = dest.read_bytes()
                entry.update(status=200, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), cached=True)
            print(f'  ok   {doc["file"]:<34} {entry.get("bytes") or "":>9}')
        except urllib.error.HTTPError as exc:
            entry.update(status=exc.code, error=str(exc))
            failed.append(doc["file"])
            print(f'  FAIL {doc["file"]:<34} HTTP {exc.code}')
        except Exception as exc:  # 超时、DNS 等
            entry.update(status=None, error=str(exc))
            failed.append(doc["file"])
            print(f'  FAIL {doc["file"]:<34} {exc}')
        index.append(entry)

    out = {
        "source": "Hong Kong Education Bureau (EDB) curriculum documents",
        "index_page": BASE + "/en/curriculum-development/kla/",
        "fetched": date.today().isoformat(),
        "note": "PDF 不入库（政府版权文件），只保留清单与链接；用 scripts/fetch_hk_edb.py 重新下载。",
        "documents": index,
    }
    path = OUT_DIR / "syllabus-index.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(index) - len(failed)}/{len(index)} ok -> {path.relative_to(ROOT)}")
    if failed:
        print("失败：", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
