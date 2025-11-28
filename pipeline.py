from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Sequence

from keyword_extractor import extract_keywords, expand_related_terms
from law_api import fetch_daily_terms, fetch_daily_to_legal, fetch_legal_to_article
from local_cache import local_daily_candidates


MAX_DAILY_PAGES = int(os.getenv("LAWGO_MAX_PAGES", "1") or "1")
DAILY_PER_PAGE = int(os.getenv("LAWGO_PER_PAGE", "20") or "20")
SEARCH_BUDGET_SEC = float(os.getenv("LAWGO_SEARCH_BUDGET", "6") or "6")


def _pick_summary(contents: Sequence[str], limit: int = 160) -> str:
    for text in contents:
        if not text:
            continue
        cleaned = text.replace("\n", " ").strip()
        if not cleaned:
            continue
        # 문장 단위로 자르고, 기본 요약 길이 제한 적용
        for split_char in (". ", "。", "…", "!", "?"):
            if split_char in cleaned:
                cleaned = cleaned.split(split_char)[0]
                break
        if len(cleaned) > limit:
            return cleaned[: limit - 1] + "…"
        return cleaned
    return ""


def run_pipeline(
    text: str,
    top_k: int = 8,
    daily_per_keyword: int = 3,
    legal_per_daily: int = 5,
) -> Dict[str, Any]:
    """
    순차 0-3-4 파이프라인.
    1) 키워드 추출
    2) 1(dlytrm)으로 일상어 후보 수집
    3) 3(dlytrmRlt)으로 법령어 후보 수집
    4) 4(lstrmRltJo) 조문으로 맥락 요약 제공
    """

    # 원문 내 단어만 사용: 확장/유사어는 비활성화 (검색 확장은 token 단위로 별도 처리)
    tokens = extract_keywords(text, top_k=top_k, expand_synonyms=False)
    warnings: List[str] = []

    keyword_bundles: List[Dict[str, Any]] = []

    def _fetch_all_daily(
        term: str,
        per_page: int = DAILY_PER_PAGE,
        max_pages: int = MAX_DAILY_PAGES,
    ) -> list[dict[str, Any]]:
        """일상용어를 페이지 단위로 수집 (환경변수로 페이지 수/크기 조절)."""
        items: list[dict[str, Any]] = []
        page = 1
        total_count = None
        start = time.monotonic()
        while page <= max_pages:
            if time.monotonic() - start > SEARCH_BUDGET_SEC:
                warnings.append(f"daily search timeout for '{term}' (>{SEARCH_BUDGET_SEC}s)")
                break
            try:
                result = fetch_daily_terms(term, page=page, num_rows=per_page)
            except Exception as exc:  # pragma: no cover - network/IO paths
                warnings.append(f"daily search failed for '{term}': {exc}")
                break

            batch = result.get("items", [])
            items.extend(batch)
            total_count = result.get("total_count") or total_count

            if total_count and len(items) >= total_count:
                break
            if len(batch) < per_page:  # 마지막 페이지
                break
            page += 1

        return items

    for tok in tokens:
        daily_candidates: List[Dict[str, Any]] = []
        seen_daily_ids = set()

        # 0) 로컬 캐시 기반 일상어 후보 우선 사용 (네트워크 호출 없이 빠르게)
        local_daily = local_daily_candidates(tok, max_daily=daily_per_keyword * 2)
        for item in local_daily:
            did = item.get("id")
            if did and did not in seen_daily_ids:
                seen_daily_ids.add(did)
                daily_candidates.append(item)

        # 원본 토큰 + 관련 확장어를 순차적으로 검색, 모자라면 이어붙임
        search_terms = [tok] + expand_related_terms(tok)
        for term in search_terms:
            daily_items = _fetch_all_daily(term, per_page=max(20, daily_per_keyword))

            for daily_item in daily_items:
                daily_id = daily_item.get("id")
                if not daily_id or daily_id in seen_daily_ids:
                    continue
                seen_daily_ids.add(daily_id)

                legal_candidates: List[Dict[str, Any]] = []
                try:
                    mapped = fetch_daily_to_legal(daily_id)
                except Exception as exc:  # pragma: no cover - network/IO paths
                    warnings.append(f"daily->legal failed for '{daily_id}': {exc}")
                    mapped = {"legal_terms": []}

                for legal in mapped.get("legal_terms", [])[:legal_per_daily]:
                    legal_id = legal.get("id")
                    if not legal_id:
                        continue
                    try:
                        article_result = fetch_legal_to_article(legal_id)
                    except Exception as exc:  # pragma: no cover - network/IO paths
                        warnings.append(f"legal->article failed for '{legal_id}': {exc}")
                        article_result = {"articles": []}

                    articles = article_result.get("articles", [])
                    summary = _pick_summary([a.get("content", "") for a in articles])
                    legal_candidates.append(
                        {
                            **legal,
                            "articles": articles,
                            "summary": summary,
                            "legal_term_name": article_result.get("legal_term_name", legal.get("name", "")),
                        }
                    )

                daily_candidates.append({**daily_item, "keyword": tok, "legal_terms": legal_candidates})

        keyword_bundles.append({"token": tok, "daily_terms": daily_candidates})

    return {
        "tokens": keyword_bundles,
        "keywords": tokens,  # backwards compatibility
        "warnings": warnings,
    }
