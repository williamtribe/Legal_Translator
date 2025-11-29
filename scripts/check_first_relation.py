#!/usr/bin/env python3
"""
data/lstrm.jsonl 첫 번째 법령용어의 일상용어 연계가 존재하는지 단건 확인하는 스크립트.

사용:
  LAWGO_OC=your_key python3 scripts/check_first_relation.py [--path data/lstrm.jsonl]
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Iterable, List

import requests


def _load_env_file(paths: list[str] | None = None) -> None:
    """간단한 .env 로더: KEY=VAL 또는 KEY = VAL 형태를 지원."""
    if paths is None:
        paths = [".env"]
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            continue


def _iter_dict_lists(obj: Any) -> Iterable[List[Dict[str, Any]]]:
    """JSON 응답에서 dict list만 뽑아내는 얕은 순회."""
    if isinstance(obj, dict):
        for val in obj.values():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                yield val  # type: ignore[misc]
            elif isinstance(val, dict):
                yield from _iter_dict_lists(val)
    elif isinstance(obj, list):
        for val in obj:
            yield from _iter_dict_lists(val)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check relations for a term in lstrm.jsonl (default: first)")
    parser.add_argument("--path", default="data/lstrm.jsonl", help="법령용어 목록 경로 (기본: data/lstrm.jsonl)")
    parser.add_argument("--timeout", nargs=2, type=float, metavar=("CONNECT", "READ"), default=(3.0, 6.0))
    parser.add_argument("--sleep", type=float, default=0.2, help="(미사용) interface compatibility")
    parser.add_argument("--index", type=int, default=0, help="확인할 행 인덱스 (0-based, 기본 0=첫 번째)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _load_env_file()
    oc = os.getenv("LAWGO_OC")
    if not oc:
        raise SystemExit("LAWGO_OC 환경변수를 설정하세요.")

    if not os.path.exists(args.path):
        raise SystemExit(f"파일을 찾을 수 없습니다: {args.path}")

    target_row = None
    with open(args.path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if idx < args.index:
                continue
            line = line.strip()
            if not line:
                continue
            target_row = json.loads(line)
            break
    if target_row is None:
        raise SystemExit(f"{args.path}에서 index={args.index} 위치의 행을 찾을 수 없습니다.")

    raw_id = target_row.get("id") or target_row.get("법령용어ID") or target_row.get("법령용어id") or ""
    name = target_row.get("name") or target_row.get("법령용어명") or ""
    ids = [p for p in raw_id.replace(" ", "").split(",") if p]
    if not ids:
        raise SystemExit("법령용어ID를 찾지 못했습니다.")

    total_relations = 0
    per_id_counts: dict[str, int] = {}
    for mst in ids:
        url = f"https://www.law.go.kr/DRF/lawService.do?OC={oc}&target=lstrmRlt&type=JSON&MST={mst}"
        res = requests.get(url, timeout=(args.timeout[0], args.timeout[1]))
        res.raise_for_status()
        data = res.json()
        lists = list(_iter_dict_lists(data))
        count = len(lists[0]) if lists else 0
        per_id_counts[mst] = count
        total_relations += count

    print(f"[term index={args.index}] name={name} id(s)={','.join(ids)}")
    print(f"relations per MST: {per_id_counts}")
    if total_relations == 0:
        print("→ 일상용어 연계가 없습니다.")
    else:
        print(f"→ 총 {total_relations}개의 일상용어 연계가 있습니다.")


if __name__ == "__main__":
    main()
