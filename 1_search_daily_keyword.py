# 1_search_daily_terms.py
"""
일상용어 조회 API (dlytrm)
- 특정 query로 검색
- 페이지네이션 처리
- XML → Python dict 변환
"""

import requests
import xml.etree.ElementTree as ET
from typing import List, Dict

OC = "turtle816"   # OC 값


# -------------------------------------------------
# XML → dict 변환 함수
# -------------------------------------------------
def parse_dlytrm_item(node):
    """일상용어(dlytrm) XML 항목 파싱"""

    # 1) attribute에서 id 찾기 (드물지만 있을 수 있음)
    item_id = node.attrib.get("id", "")

    # 2) <id> 태그에서 찾기
    id_tag = node.find("id")
    if id_tag is not None and id_tag.text:
        item_id = id_tag.text.strip()

    def safe_text(tagname):
        child = node.find(tagname)
        if child is not None and child.text:
            return child.text.strip()
        for c in node:
            if tagname.replace(" ", "") in c.tag.replace(" ", ""):
                return (c.text or "").strip()
        return ""

    return {
        "일상용어id": item_id,
        "일상용어명": safe_text("일상용어명"),
        "출처": safe_text("출처"),
        "용어간관계링크": safe_text("용어간관계링크"),
    }


# -------------------------------------------------
# API 요청 함수
# -------------------------------------------------
def fetch_daily_terms(keyword="*", page=1, num_rows=100):
    """일상용어 검색 (dlytrm)"""

    url = (
        "https://www.law.go.kr/DRF/lawSearch.do"
        f"?OC={OC}&target=dlytrm&type=XML"
        f"&query={keyword}"
        f"&display={num_rows}"
        f"&page={page}"
    )

    res = requests.get(url)
    res.raise_for_status()

    root = ET.fromstring(res.text)

    total_count = int(root.findtext("검색결과개수", 0))

    items = []
    for child in root:
        if "일상용어" in child.tag:
            items.append(parse_dlytrm_item(child))

    return {
        "total_count": total_count,
        "items": items
    }


# -------------------------------------------------
# 전체 페이지 수집 함수
# -------------------------------------------------
def fetch_all_daily_terms(keyword="*", max_rows=100) -> List[Dict]:
    first = fetch_daily_terms(keyword, page=1, num_rows=max_rows)
    total_count = first["total_count"]
    results = first["items"]

    print(f"[INFO] 검색어 '{keyword}' → 총 {total_count}건")

    total_pages = (total_count // max_rows) + 1

    for page in range(2, total_pages + 1):
        print(f"[INFO] Collecting page {page}/{total_pages} ...")
        data = fetch_daily_terms(keyword, page=page, num_rows=max_rows)
        results.extend(data["items"])

    print(f"[INFO] 최종 수집 일상용어 개수: {len(results)}")
    return results


# -------------------------------------------------
# 실행 테스트
# -------------------------------------------------
if __name__ == "__main__":
    items = fetch_daily_terms("보험")  # 테스트
    print(items["items"][:5])
