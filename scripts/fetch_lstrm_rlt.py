"""
법령용어(lstrm) 수집과 법령→일상 용어 연계(lstrmRlt) 수집을 분리 실행한다.

실행 전 준비:
  export LAWGO_OC=your_key

사용 예:
  # 1단계: 법령용어 목록만 수집
  python3 scripts/fetch_lstrm_rlt.py lstrm --out-dir data --sleep 0.3 --timeout 3 6

  # 2단계: 수집된 법령용어 개수를 확인한 뒤, 일상용어 연계를 이어받아 수집
  python3 scripts/fetch_lstrm_rlt.py relations --out-dir data --resume --sleep 0.1 --timeout 3 6

추가 옵션:
  # query=* 풀스캔 모드 또는 gana+query 합집합 수집
  python3 scripts/fetch_lstrm_rlt.py lstrm --strategy query --out-dir data --sleep 0.3 --timeout 3 6
  python3 scripts/fetch_lstrm_rlt.py lstrm --strategy both --out-dir data --sleep 0.3 --timeout 3 6

출력:
  data/lstrm.jsonl        # 법령용어 ID/명/사전구분/정의(가능하면) 등
  data/lstrm_rlt.jsonl    # 법령용어-일상용어 연결 (관계코드/명 포함)
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, Iterable, List

import requests

GANA_CODES = ["ga", "na", "da", "ra", "ma", "ba", "sa", "aa", "ja", "cha", "ka", "ta", "pa", "ha"]


def _env(key: str, default: str = "") -> str:
    val = os.getenv(key)
    return val.strip() if val else default


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
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            # .env 파싱 실패 시 조용히 넘어간다.
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


def _get(item: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in item and item[key]:
            return str(item[key]).strip()
    return ""


def _fetch_json(url: str, timeout: tuple[float, float], retries: int, sleep_sec: float, label: str) -> Dict[str, Any]:
    """HTTP GET with retry/backoff, returns {} on repeated failure."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(url, timeout=timeout)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.HTTPError as exc:  # pragma: no cover - network
            status = exc.response.status_code if exc.response is not None else None
            if status == 404:
                print(f"[warn] {label} returned 404. skipping retries.")
                return {}
            last_exc = exc
            wait = sleep_sec * attempt
            print(
                f"[warn] {label} attempt {attempt}/{retries} failed with status {status}: {exc}. retrying in {wait:.1f}s"
            )
            time.sleep(wait)
        except Exception as exc:  # pragma: no cover - network
            last_exc = exc
            wait = sleep_sec * attempt
            print(f"[warn] {label} attempt {attempt}/{retries} failed: {exc}. retrying in {wait:.1f}s")
            time.sleep(wait)
    print(f"[error] {label} failed after {retries} retries: {last_exc}")
    return {}


def fetch_lstrm_page(
    oc: str, gana: str, page: int, display: int, timeout: tuple[float, float], retries: int, sleep_sec: float
) -> Dict[str, Any]:
    url = (
        "https://www.law.go.kr/DRF/lawSearch.do"
        f"?OC={oc}&target=lstrm&type=JSON&gana={gana}&display={display}&page={page}"
    )
    return _fetch_json(url, timeout=timeout, retries=retries, sleep_sec=sleep_sec, label=f"lstrm {gana}/{page}")


def fetch_lstrm_page_query(
    oc: str, page: int, display: int, timeout: tuple[float, float], retries: int, sleep_sec: float
) -> Dict[str, Any]:
    url = (
        "https://www.law.go.kr/DRF/lawSearch.do"
        f"?OC={oc}&target=lstrm&type=JSON&query=*&display={display}&page={page}"
    )
    return _fetch_json(url, timeout=timeout, retries=retries, sleep_sec=sleep_sec, label=f"lstrm query=*/{page}")


def fetch_lstrm_ai_page(
    oc: str, page: int, display: int, timeout: tuple[float, float], retries: int, sleep_sec: float
) -> Dict[str, Any]:
    url = (
        "https://www.law.go.kr/DRF/lawSearch.do"
        f"?OC={oc}&target=lstrmAI&type=JSON&query=*&display={display}&page={page}"
    )
    return _fetch_json(url, timeout=timeout, retries=retries, sleep_sec=sleep_sec, label=f"lstrmAI */{page}")


def fetch_lstrm_rlt(oc: str, mst: str, timeout: tuple[float, float], retries: int, sleep_sec: float) -> Dict[str, Any]:
    url = f"https://www.law.go.kr/DRF/lawService.do?OC={oc}&target=lstrmRlt&type=JSON&MST={mst}"
    return _fetch_json(url, timeout=timeout, retries=retries, sleep_sec=sleep_sec, label=f"lstrmRlt {mst}")


def collect_lstrm(
    oc: str,
    display: int,
    timeout: tuple[float, float],
    sleep_sec: float,
    retries: int,
    strategy: str = "gana",
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    def _collect_gana() -> None:
        for gana in GANA_CODES:
            page = 1
            while True:
                data = fetch_lstrm_page(oc, gana, page, display, timeout, retries, sleep_sec)
                if not data:
                    break
                lists = list(_iter_dict_lists(data))
                if not lists:
                    break
                items = lists[0]  # 가장 상위 리스트를 사용
                if not items:
                    break

                for item in items:
                    lid = _get(item, "법령용어ID", "법령용어id", "id")
                    name = _get(item, "법령용어명", "법령용어")
                    if not lid or lid in seen_ids:
                        continue
                    seen_ids.add(lid)
                    results.append(
                        {
                            "id": lid,
                            "name": name,
                            "note": _get(item, "비고", "법령용어상세검색"),
                            "dict_kind_code": _get(item, "사전구분코드"),
                            "law_kind_code": _get(item, "법령종류코드"),
                        }
                    )

                if len(items) < display:
                    break
                page += 1
                time.sleep(sleep_sec)

    def _collect_query_all() -> None:
        page = 1
        while True:
            data = fetch_lstrm_page_query(oc, page, display, timeout, retries, sleep_sec)
            if not data:
                break
            lists = list(_iter_dict_lists(data))
            if not lists:
                break
            items = lists[0]
            if not items:
                break
            for item in items:
                lid = _get(item, "법령용어ID", "법령용어id", "id")
                name = _get(item, "법령용어명", "법령용어")
                if not lid or lid in seen_ids:
                    continue
                seen_ids.add(lid)
                results.append(
                    {
                        "id": lid,
                        "name": name,
                        "note": _get(item, "비고", "법령용어상세검색"),
                        "dict_kind_code": _get(item, "사전구분코드"),
                        "law_kind_code": _get(item, "법령종류코드"),
                    }
                )
            if len(items) < display:
                break
            page += 1
            time.sleep(sleep_sec)

    if strategy == "gana":
        _collect_gana()
    elif strategy == "query":
        _collect_query_all()
    elif strategy == "both":
        _collect_gana()
        _collect_query_all()
    elif strategy == "ai":
        # lstrmAI로 query=* 풀스캔
        page = 1
        while True:
            data = fetch_lstrm_ai_page(oc, page, display, timeout, retries, sleep_sec)
            if not data:
                break
            # lstrmAISearch 루트에서 '법령용어' 리스트 추출
            items: list[dict[str, Any]] = []
            for val in data.values():
                if isinstance(val, dict) and "법령용어" in val and isinstance(val["법령용어"], list):
                    items = val["법령용어"]
                    break
            if not items:
                break

            for item in items:
                link = _get(item, "용어간관계링크")
                mst = ""
                if link and "MST=" in link:
                    try:
                        import urllib.parse as up

                        qs = up.urlparse(link).query
                        mst = up.parse_qs(qs).get("MST", [""])[0]
                    except Exception:
                        mst = ""
                lid = mst or _get(item, "법령용어ID", "법령용어id", "id")
                name = _get(item, "법령용어명", "법령용어")
                if not lid or lid in seen_ids:
                    continue
                seen_ids.add(lid)
                results.append(
                    {
                        "id": lid,
                        "name": name,
                        "note": _get(item, "비고"),
                        "dict_kind_code": _get(item, "사전구분코드"),  # lstrmAI 응답에는 없지만 키 확보
                        "law_kind_code": _get(item, "법령종류코드"),
                        "relation_link": link,
                        "article_link": _get(item, "조문간관계링크"),
                        "raw_id": _get(item, "id"),
                    }
                )
            if len(items) < display:
                break
            page += 1
            time.sleep(sleep_sec)
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown strategy: {strategy}")
    return results


def collect_relations(
    oc: str,
    legal_terms: list[dict[str, str]],
    timeout: tuple[float, float],
    sleep_sec: float,
    retries: int,
    processed_ids: set[str] | None = None,
    out_path: str | None = None,
    flush_every: int = 200,
) -> list[dict[str, str]]:
    """
    법령용어별 일상용어 연계를 수집.
    processed_ids가 있으면 해당 법령용어ID는 건너뜀.
    out_path가 있으면 실시간 append; 없으면 리스트로 반환.
    """
    results: list[dict[str, str]] = []
    processed_ids = processed_ids or set()
    writer = None
    written = 0
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        writer = open(out_path, "a", encoding="utf-8")

    def _write(row: dict[str, str]) -> None:
        nonlocal written
        if writer:
            writer.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
            if written % flush_every == 0:
                writer.flush()
        else:
            results.append(row)

    for term in legal_terms:
        raw_id = term.get("id") or term.get("법령용어ID") or term.get("법령용어id") or ""
        if not raw_id:
            continue
        parts = [p for p in raw_id.replace(" ", "").split(",") if p]
        for mst in parts:
            if mst in processed_ids:
                continue
            data = fetch_lstrm_rlt(oc, mst, timeout, retries, sleep_sec)
            lists = list(_iter_dict_lists(data))
            if not lists:
                time.sleep(sleep_sec)
                continue
            items = lists[0]
            for item in items:
                daily_id = _get(item, "연계용어id", "id", "일상용어id")
                daily_name = _get(item, "일상용어명", "연계용어명")
                if not daily_id and not daily_name:
                    continue
                _write(
                    {
                        "legal_id": mst,
                        "legal_name": term.get("name", ""),
                        "daily_id": daily_id,
                        "daily_name": daily_name,
                        "relation_code": _get(item, "용어관계코드"),
                        "relation": _get(item, "용어관계"),
                    }
                )
            processed_ids.add(mst)
            time.sleep(sleep_sec)

    if writer:
        writer.flush()
        writer.close()
    return results


def save_jsonl(path: str, rows: Iterable[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_jsonl(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    rows: list[dict[str, Any]] = []
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


def _add_common_fetch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", default="data", help="출력 디렉토리 (기본: data)")
    parser.add_argument("--sleep", type=float, default=0.3, help="요청 간 대기 (초)")
    parser.add_argument(
        "--timeout",
        nargs=2,
        type=float,
        metavar=("CONNECT", "READ"),
        default=None,
        help="requests timeout (connect, read). 기본값은 env LAWGO_CONNECT_TIMEOUT / LAWGO_READ_TIMEOUT 또는 (3, 6)",
    )
    parser.add_argument("--retries", type=int, default=3, help="요청 실패 시 재시도 횟수 (기본 3)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch law terms (lstrm) or their daily-term relations (lstrmRlt).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lstrm_parser = subparsers.add_parser("lstrm", help="법령용어(lstrm) 목록만 수집")
    _add_common_fetch_args(lstrm_parser)
    lstrm_parser.add_argument("--display", type=int, default=100, help="페이지 당 조회 건수 (기본 100, 최대 100)")
    lstrm_parser.add_argument(
        "--strategy",
        choices=["gana", "query", "both", "ai"],
        default="gana",
        help="lstrm 수집 전략: gana(초성별), query(query=* 풀스캔), both(합집합), ai(lstrmAI query=*) (기본 gana)",
    )

    relation_parser = subparsers.add_parser("relations", help="법령→일상 용어 연계(lstrmRlt)만 수집")
    _add_common_fetch_args(relation_parser)
    relation_parser.add_argument(
        "--max-terms",
        type=int,
        default=None,
        help="lstrm 상위 N개만 처리 (테스트/부분 수집용)",
    )
    relation_parser.add_argument(
        "--flush-every",
        type=int,
        default=200,
        help="append 모드에서 몇 개마다 flush할지 (기본 200)",
    )
    relation_parser.add_argument(
        "--resume",
        action="store_true",
        help="기존 lstrm_rlt.jsonl을 읽어 이미 처리한 법령ID는 건너뜀 (append 모드)",
    )
    relation_parser.add_argument(
        "--lstrm-path",
        default=None,
        help="법령용어 목록 경로 (기본: <out-dir>/lstrm.jsonl)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _load_env_file()
    oc = _env("LAWGO_OC")
    if not oc:
        raise SystemExit("LAWGO_OC 환경변수를 설정하세요.")

    connect_timeout = _env("LAWGO_CONNECT_TIMEOUT", "3")
    read_timeout = _env("LAWGO_READ_TIMEOUT", "6")
    timeout = (
        float(connect_timeout),
        float(read_timeout),
    )
    if args.timeout:
        timeout = (args.timeout[0], args.timeout[1])

    if args.command == "lstrm":
        lstrm_path = os.path.join(args.out_dir, "lstrm.jsonl")
        print(f"[lstrm] Fetching strategy={args.strategy} (display={args.display})...")
        legal_terms = collect_lstrm(
            oc,
            display=args.display,
            timeout=timeout,
            sleep_sec=args.sleep,
            retries=args.retries,
            strategy=args.strategy,
        )
        save_jsonl(lstrm_path, legal_terms)
        print(f"[lstrm] saved {len(legal_terms)} terms -> {lstrm_path}")
        return

    lstrm_path = args.lstrm_path or os.path.join(args.out_dir, "lstrm.jsonl")
    rlt_path = os.path.join(args.out_dir, "lstrm_rlt.jsonl")
    if not os.path.exists(lstrm_path):
        raise SystemExit(f"법령용어 목록이 필요합니다: {lstrm_path}")

    legal_terms = load_jsonl(lstrm_path)
    print(f"[relations] Loaded {len(legal_terms)} legal terms from {lstrm_path}")

    if args.max_terms:
        legal_terms = legal_terms[: args.max_terms]
        print(f"[relations] processing first {len(legal_terms)} terms due to --max-terms")

    if not legal_terms:
        print("[relations] No legal terms to process. Exiting.")
        return

    processed_ids: set[str] = set()
    if args.resume and os.path.exists(rlt_path):
        existing = load_jsonl(rlt_path)
        for row in existing:
            lid = row.get("legal_id") or row.get("법령용어ID") or row.get("법령용어id")
            if lid:
                processed_ids.add(str(lid))
        print(f"[resume] skipping {len(processed_ids)} already processed legal_ids from {rlt_path}")

    print(f"[relations] Fetching lstrmRlt for each term...")
    relations = collect_relations(
        oc,
        legal_terms,
        timeout=timeout,
        sleep_sec=args.sleep,
        retries=args.retries,
        processed_ids=processed_ids,
        out_path=rlt_path if args.resume else None,
        flush_every=args.flush_every,
    )
    if not args.resume:
        save_jsonl(rlt_path, relations)
    print(f"[relations] saved {len(relations) if not args.resume else 'append-mode'} relations -> {rlt_path}")


if __name__ == "__main__":
    main()
