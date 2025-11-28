# 0_search_legal_keyword.py
"""
법령정보지식베이스 - 법령용어 조회 API (lstrmAI)
"""

import requests
import xml.etree.ElementTree as ET
from typing import List, Dict

OC = "turtle816"


# -------------------------------------------------
# XML → dict 변환 함수
# -------------------------------------------------
def parse_lstrmAI_item(node):
    term_id = node.attrib.get("id", "")

    # 태그 특성상 공백·제어문자 들어가는 경우가 있어 정규화 처리
    def safe_text(tagname):
        # 1차: 정확히 찾기
        child = node.find(tagname)
        if child is not None and child.text:
            return child.text.strip()

        # 2차: 공백 제거 후 매칭
        target_norm = tagname.replace(" ", "")
        for c in node:
            if target_norm in c.tag.replace(" ", ""):
                return (c.text or "").strip()

        return ""

    return {
        "법령용어id": term_id,
        "법령용어명": safe_text("법령용어명"),
        "동음이의어존재여부": safe_text("동음이의어존재여부"),
        "비고": safe_text("비고"),
        "용어간관계링크": safe_text("용어간관계링크"),
        "조문간관계링크": safe_text("조문간관계링크"),
    }


# -------------------------------------------------
# API 요청 함수
# -------------------------------------------------
def fetch_legal_terms(keyword: str, page: int = 1, num_rows: int = 100) -> Dict:

    url = (
        "https://www.law.go.kr/DRF/lawSearch.do"
        f"?OC={OC}&target=lstrmAI&type=XML"
        f"&query={keyword}"
        f"&display={num_rows}"
        f"&page={page}"
    )

    res = requests.get(url)
    res.raise_for_status()

    root = ET.fromstring(res.text)

    # 전체 건수
    total_count = int(root.findtext("검색결과개수", 0))

    # ---------------------------
    # 핵심 수정 포인트: 법령용어 태그 수집
    # ---------------------------
    items = []
    for child in root:
        # 태그 이름에 공백, BOM, 제어문자 등이 있어도 매칭되도록
        if "법령용어" in child.tag:
            items.append(parse_lstrmAI_item(child))

    return {
        "total_count": total_count,
        "items": items
    }


# -------------------------------------------------
# 전체 페이지 수집 함수
# -------------------------------------------------
def fetch_all_legal_terms(keyword: str, max_rows: int = 100) -> List[Dict]:
    first = fetch_legal_terms(keyword, page=1, num_rows=max_rows)
    total_count = first["total_count"]
    results = first["items"]

    print(f"[INFO] 검색어 '{keyword}' → 총 {total_count}건")
    total_pages = (total_count // max_rows) + 1

    for page in range(2, total_pages + 1):
        print(f"[INFO] Collecting page {page}/{total_pages} ...")
        data = fetch_legal_terms(keyword, page=page, num_rows=max_rows)
        results.extend(data["items"])

    print(f"[INFO] 최종 수집 용어 개수: {len(results)}")
    return results


# -------------------------------------------------
# 실행 예시
# -------------------------------------------------
if __name__ == "__main__":
    keyword = "배상"
    items = fetch_all_legal_terms(keyword, max_rows=100)

    for item in items[:10]:
        print(item)
