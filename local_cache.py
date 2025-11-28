"""
로컬 JSONL 캐시(lstrm, lstrm_rlt)를 읽어 일상/법령어 후보를 빠르게 조회하기 위한 헬퍼.

환경변수:
  LAWGO_DATA_DIR: 기본 data 디렉터리 위치 (default: "data")
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, Iterable, List


DATA_DIR = os.getenv("LAWGO_DATA_DIR", "data")
LSTRM_PATH = os.path.join(DATA_DIR, "lstrm.jsonl")
LSTRM_RLT_PATH = os.path.join(DATA_DIR, "lstrm_rlt.jsonl")


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


@lru_cache(maxsize=1)
def load_legal_terms() -> List[Dict[str, Any]]:
    return _read_jsonl(LSTRM_PATH)


@lru_cache(maxsize=1)
def load_relations() -> List[Dict[str, Any]]:
    return _read_jsonl(LSTRM_RLT_PATH)


@lru_cache(maxsize=1)
def _legal_index_by_id() -> Dict[str, Dict[str, Any]]:
    return {row.get("id") or row.get("법령용어ID"): row for row in load_legal_terms() if row.get("id") or row.get("법령용어ID")}


@lru_cache(maxsize=1)
def _relations_by_legal() -> Dict[str, List[Dict[str, Any]]]:
    rels = load_relations()
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rels:
        lid = row.get("legal_id") or row.get("법령용어id") or row.get("법령용어ID")
        if not lid:
            continue
        grouped.setdefault(lid, []).append(row)
    return grouped


def _matches(token: str, name: str) -> bool:
    token = token.strip()
    name = name.strip()
    if not token or not name:
        return False
    return token in name


def local_daily_candidates(token: str, max_daily: int = 30, max_legal: int = 50) -> List[Dict[str, Any]]:
    """
    토큰을 포함하는 법령용어명 기반으로 일상용어 후보를 로컬 캐시에서 찾는다.
    반환 형식은 pipeline의 daily_candidates와 유사하게 맞춘다.
    """
    token = token.strip()
    if not token:
        return []

    legal_terms = load_legal_terms()
    rel_by_legal = _relations_by_legal()
    daily_map: Dict[str, Dict[str, Any]] = {}

    matched_legal = [lt for lt in legal_terms if _matches(token, str(lt.get("name") or lt.get("법령용어명") or ""))]
    matched_legal = matched_legal[:max_legal]

    for lt in matched_legal:
        lid = lt.get("id") or lt.get("법령용어ID") or lt.get("법령용어id")
        lname = lt.get("name") or lt.get("법령용어명") or ""
        if not lid:
            continue
        relations = rel_by_legal.get(lid, [])
        for rel in relations:
            daily_id = rel.get("daily_id") or rel.get("연계용어id") or rel.get("일상용어id")
            daily_name = rel.get("daily_name") or rel.get("일상용어명") or rel.get("연계용어명")
            if not daily_name:
                continue
            entry = daily_map.get(daily_id or daily_name)
            legal_entry = {
                "id": lid,
                "name": lname,
                "relation_code": rel.get("relation_code") or rel.get("용어관계코드"),
                "relation": rel.get("relation") or rel.get("용어관계"),
                "note": lt.get("note") or "",
            }
            if entry is None:
                daily_map[daily_id or daily_name] = {
                    "id": daily_id or daily_name,
                    "name": daily_name,
                    "source": "cache:lstrmRlt",
                    "stem_relation_link": "",
                    "keyword": token,
                    "legal_terms": [legal_entry],
                }
            else:
                # 동일 일상어에 다른 법령어 연결 추가
                entry.setdefault("legal_terms", []).append(legal_entry)

            if len(daily_map) >= max_daily:
                break
        if len(daily_map) >= max_daily:
            break

    return list(daily_map.values())
