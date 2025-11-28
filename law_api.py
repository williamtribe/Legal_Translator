from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests


def _timeout() -> tuple[float, float]:
    """Env-configurable timeout (connect, read). Shorter 기본값으로 응답 지연을 줄인다."""
    return (
        float(os.getenv("LAWGO_CONNECT_TIMEOUT", "3")),
        float(os.getenv("LAWGO_READ_TIMEOUT", "6")),
    )


def _norm(value: str) -> str:
    return (value or "").replace(" ", "").strip()


def _find_text(node: ET.Element, *candidates: str) -> str:
    for cand in candidates:
        if not cand:
            continue
        text = node.findtext(cand)
        if text:
            return text.strip()

    norm_candidates = [_norm(c) for c in candidates if c]
    for child in node:
        tag_norm = _norm(child.tag)
        if any(c in tag_norm for c in norm_candidates):
            return (child.text or "").strip()
    return ""


def _int_or_zero(value: Optional[str]) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _fetch_xml(url: str) -> ET.Element:
    res = requests.get(url, timeout=_timeout())
    res.raise_for_status()
    return ET.fromstring(res.text)


def _pick_total_count(root: ET.Element) -> int:
    tags = ("검색결과개수", "검색결과수", "전체건수", "totalCnt", "count")
    for tag in tags:
        text = root.findtext(tag)
        if text:
            return _int_or_zero(text)

    for child in root:
        if "total" in _norm(child.tag):
            return _int_or_zero(child.text)
    return 0


def get_oc() -> str:
    for key in ("LAWGO_OC", "LAWGO_ACCESS_KEY", "ACCESS_KEY", "access_key"):
        val = os.getenv(key)
        if val:
            return val.strip()
    return "turtle816"


def fetch_daily_terms(keyword: str, page: int = 1, num_rows: int = 20) -> Dict[str, Any]:
    oc = get_oc()
    url = (
        "https://www.law.go.kr/DRF/lawSearch.do"
        f"?OC={oc}&target=dlytrm&type=XML&query={keyword}&display={num_rows}&page={page}"
    )
    root = _fetch_xml(url)
    total_count = _pick_total_count(root)

    items: List[Dict[str, str]] = []
    for child in root:
        if "일상용어" in _norm(child.tag):
            items.append(
                {
                    "id": child.attrib.get("id") or _find_text(child, "id"),
                    "name": _find_text(child, "일상용어명", "일상용어"),
                    "source": _find_text(child, "출처"),
                    "stem_relation_link": _find_text(child, "어간관계링크", "어간관계링크"),
                }
            )

    return {"total_count": total_count, "items": items}


def fetch_daily_to_legal(daily_term_id: str) -> Dict[str, Any]:
    oc = get_oc()
    url = (
        "https://www.law.go.kr/DRF/lawService.do"
        f"?OC={oc}&target=dlytrmRlt&type=XML&MST={daily_term_id}"
    )

    root = _fetch_xml(url)
    daily_node = None
    for child in root:
        if "일상용어" in _norm(child.tag):
            daily_node = child
            break

    if daily_node is None:
        return {"daily_term_id": daily_term_id, "daily_term_name": "", "source": "", "legal_terms": []}

    legal_terms: List[Dict[str, str]] = []
    for rel_node in daily_node:
        tag_norm = _norm(rel_node.tag)
        if not any(key in tag_norm for key in ("관련", "연계", "관계용어")):
            continue
        legal_terms.append(
            {
                "id": rel_node.attrib.get("id")
                or _find_text(rel_node, "관련용어id", "법령용어id", "법령용어코드"),
                "name": _find_text(rel_node, "법령용어명", "법령용어"),
                "relation_code": _find_text(rel_node, "용어관계코드"),
                "relation": _find_text(rel_node, "용어관계"),
                "note": _find_text(rel_node, "비고"),
            }
        )

    return {
        "daily_term_id": daily_term_id,
        "daily_term_name": _find_text(daily_node, "일상용어명", "일상용어"),
        "source": _find_text(daily_node, "출처"),
        "legal_terms": legal_terms,
    }


def fetch_legal_to_article(legal_term_id: str) -> Dict[str, Any]:
    oc = get_oc()
    url = (
        "https://www.law.go.kr/DRF/lawService.do"
        f"?OC={oc}&target=lstrmRltJo&type=XML&MST={legal_term_id}"
    )
    root = _fetch_xml(url)
    legal_node = None
    for child in root:
        if "법령용어" in _norm(child.tag):
            legal_node = child
            break

    if legal_node is None:
        return {"legal_term_id": legal_term_id, "legal_term_name": "", "articles": []}

    articles: List[Dict[str, str]] = []
    for rel_node in legal_node:
        if "관련법령" not in _norm(rel_node.tag):
            continue
        articles.append(
            {
                "law_id": rel_node.attrib.get("id") or "",
                "law_name": _find_text(rel_node, "법령명", "법령이름"),
                "article_number": _find_text(rel_node, "조번호", "조문번호"),
                "order_number": _find_text(rel_node, "조령지번호", "조직지번호"),
                "content": _find_text(rel_node, "조문내용"),
                "term_type_code": _find_text(rel_node, "용어구분코드"),
                "term_type": _find_text(rel_node, "용어구분"),
                "article_relation_link": _find_text(
                    rel_node, "조문관계어링크", "조문관계용어링크"
                ),
            }
        )

    return {
        "legal_term_id": legal_term_id,
        "legal_term_name": _find_text(legal_node, "법령용어명", "법령용어"),
        "articles": articles,
    }


def fetch_legal_terms(keyword: str, page: int = 1, num_rows: int = 20) -> Dict[str, Any]:
    oc = get_oc()
    url = (
        "https://www.law.go.kr/DRF/lawSearch.do"
        f"?OC={oc}&target=lstrmAI&type=XML&query={keyword}&display={num_rows}&page={page}"
    )
    root = _fetch_xml(url)
    total_count = _pick_total_count(root)

    items: List[Dict[str, str]] = []
    for child in root:
        if "법령용어" in _norm(child.tag):
            items.append(
                {
                    "id": child.attrib.get("id") or _find_text(child, "id"),
                    "name": _find_text(child, "법령용어명", "법령용어"),
                    "note": _find_text(child, "비고"),
                    "between_terms_link": _find_text(child, "용어관계링크"),
                    "between_articles_link": _find_text(child, "조문관계링크"),
                }
            )

    return {"total_count": total_count, "items": items}
