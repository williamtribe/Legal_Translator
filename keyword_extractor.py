from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List, Sequence, Set

try:
    from konlpy.tag import Okt  # type: ignore
except Exception:
    Okt = None  # type: ignore

_okt = None

# 기본 불용어(조사, 연결어, 일반 동사)
DEFAULT_STOPWORDS: Set[str] = {
    "그리고",
    "그러나",
    "하지만",
    "그래서",
    "그러면",
    "그런데",
    "하다",
    "되다",
    "이다",
    "있다",
    "없다",
    "않다",
    "알다",
    "같다",
    "같은",
    "거",
    "것",
    "정도",
    "부분",
    "때문",
    "관련",
    "대한",
    "이번",
    "이번에",
    "우리",
    "저희",
    "제가",
    "나는",
    "너무",
    "매우",
    "정말",
    # 의문사·의문형
    "어떻게",
    "어디",
    "언제",
    "왜",
    "무엇",
    "뭐",
    "몇",
    "누가",
    "누구",
    "어느",
    # 의문/명령 어미
    "해야",
    "해야만",
    "해야지",
    "해야하나",
    "해야되나",
    "해야되나요",
    "하나요",
    "하냐",
    "하니",
    "하네",
    "했나요",
    "했는데",
    "했습니까",
    "됩니까",
    "되나요",
}

# 단어 내 불필요 어미/조사 제거용 패턴
TRAILING_PARTICLES = re.compile(
    r"(입니다|합니다|했다|했음|했어요|했는데|했지만|하고|하며|하고|이다|였다|하나요|하냐|하니|하네|되나요|됩니까)$"
)
SINGLE_PARTICLE = re.compile(r"[이가은는을를의에와과도만까지조차부터]$")

SYNONYM_SEEDS: dict[str, Sequence[str]] = {
    "보험": ("보험금", "보험료", "보험계약", "공제", "손해보험", "자동차보험"),
    "사고": ("손해", "배상", "책임", "과실"),
    "임대": ("임대차", "월세", "전세", "보증금"),
    "전세": ("보증금", "임차인", "임대인"),
    "계약": ("계약해지", "해지", "위약금"),
    "임금": ("급여", "월급", "체불"),
    "해고": ("부당해고", "정직", "징계"),
    "대여": ("차용", "금전대여", "채무", "채권", "변제"),
    "빌리다": ("차용", "금전대여", "채무", "채권", "변제", "채무불이행"),
    "돈": ("금전", "채무", "채권", "변제"),
    "잠수": ("연락두절", "채무불이행", "기망", "사기"),
}

# 도메인 규칙 기반 확장
DOMAIN_EXPAND_RULES: list[tuple[re.Pattern, Sequence[str]]] = [
    (re.compile(r"(빌리|빌려|대여|꿔|차용)"), ("차용", "금전대여", "채무", "변제", "채권", "채무불이행")),
    (re.compile(r"(돈|금전|채무|채권)"), ("금전", "채무", "채권", "변제")),
    (re.compile(r"(잠수|연락|두절|도피)"), ("연락두절", "채무불이행", "기망", "사기")),
    (re.compile(r"(사기|기망|속임)"), ("사기", "기망", "형사", "손해배상")),
]


SEARCH_SYNONYMS: dict[str, Sequence[str]] = {
    "잠수": ("연락두절", "연락불능", "행방불명", "도피"),
    "잠수를": ("연락두절", "연락불능", "행방불명", "도피"),
    "잠수를탔다": ("연락두절", "연락불능", "행방불명", "도피"),
    "잠수를탔습니다": ("연락두절", "연락불능", "행방불명", "도피"),
    "연락": ("연락두절", "연락불능"),
    "연락이안된다": ("연락두절", "연락불능"),
    "친구": ("지인", "동료"),
    "아는": ("지인", "친구"),
    "형": ("지인", "친구"),
    "빌려줬다": ("차용", "금전대여", "채무"),
    "빌려줬는데": ("차용", "금전대여", "채무", "변제"),
    "돈": ("금전", "채무", "채권", "변제"),
    "못받았다": ("미수", "채권", "채무불이행"),
    "못받았어요": ("미수", "채권", "채무불이행"),
}


def _get_okt():
    global _okt
    if _okt is None and Okt:
        _okt = Okt()
    return _okt


def _simple_tokens(text: str) -> list[str]:
    return re.findall(r"[가-힣]{2,}|[A-Za-z0-9]{2,}", text)


def _tokenize(text: str) -> list[str]:
    okt = _get_okt()
    if okt:
        tokens: list[str] = []
        for word, tag in okt.pos(text, norm=True, stem=True):
            if tag.startswith(("J", "E", "X", "S", "F")):
                continue
            if len(word) < 2:
                continue
            tokens.append(word)
        return tokens
    return _simple_tokens(text)


def _normalize_token(token: str) -> str:
    token = token.strip()
    token = TRAILING_PARTICLES.sub("", token)
    token = SINGLE_PARTICLE.sub("", token)
    return token


# 의미 단위 분리/어간 회복: 조사/경어/서술어 어미를 걷어내고 기본형을 더해준다.
VERB_BASE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(빌려줬|빌려주었|빌려주었습|빌려줬습)"), "빌려주다"),
    (re.compile(r"(빌렸|빌려|빌리었|빌리었습|빌렸습)"), "빌리다"),
    (re.compile(r"(타였|탔|탔다|탔습|타겠)"), "타다"),
    (re.compile(r"(했|하였|합니다|했습|해요|합니다)$"), "하다"),
]

ENDINGS_TO_STRIP: tuple[str, ...] = (
    "였습니다",
    "였습니다만",
    "였습니다만",
    "이었어요",
    "이었는데",
    "이었습니다",
    "이었습니다만",
    "이었습",
    "입니다",
    "입니까",
    "입니다만",
    "였어요",
    "했어요",
    "했는데",
    "했지만",
    "했으니",
    "했으며",
    "했으나",
    "했으면",
    "했습니다",
    "했습니까",
    "했습",
    "습니다",
    "습니까",
    "습니다만",
    "는데",
    "라서",
    "이라서",
    "이라면",
    "이면",
    "이면요",
    "네요",
    "에요",
    "예요",
    "어요",
    "아서",
    "어서",
    "었어요",
    "였어요",
    "였는데",
    "겠어요",
    "겠네요",
    "겠는데",
    "겠습",
)


def _derive_meaning_units(token: str) -> List[str]:
    """추출된 토큰을 의미 단위로 잘게 쪼개고 기본형을 추가."""
    units: list[str] = []

    # 격식/어미 제거
    for ending in ENDINGS_TO_STRIP:
        if token.endswith(ending) and len(token) - len(ending) >= 2:
            stripped = token[: -len(ending)]
            if stripped not in units:
                units.append(stripped)
            token = stripped
            break

    # 동사/형용사 기본형 복원 규칙 적용
    for pattern, base in VERB_BASE_RULES:
        if pattern.search(token):
            if base not in units:
                units.append(base)

    # 하다 체계: "...하"로 끝나면 "하다" 추가
    if token.endswith("하") and "하다" not in units:
        units.append("하다")

    return [u for u in units if len(u) >= 2]


def _expand_domain(token: str) -> list[str]:
    extras: list[str] = []
    for pattern, additions in DOMAIN_EXPAND_RULES:
        if pattern.search(token):
            extras.extend(additions)
    return extras


def expand_related_terms(token: str) -> List[str]:
    """원문 토큰으로부터 검색 확장어를 생성."""
    related: List[str] = []
    if token in SEARCH_SYNONYMS:
        related.extend(SEARCH_SYNONYMS[token])
    # 도메인 규칙 기반 확장도 추가
    related.extend(_expand_domain(token))
    # 중복 제거 유지
    deduped: List[str] = []
    for r in related:
        if r not in deduped and r != token:
            deduped.append(r)
    return deduped


def extract_keywords(
    text: str,
    top_k: int = 8,
    extra_stopwords: Iterable[str] | None = None,
    expand_synonyms: bool = True,
) -> List[str]:
    """Extract legal-oriented keywords from Korean text."""

    if not text:
        return []

    stopwords: Set[str] = set(DEFAULT_STOPWORDS)
    if extra_stopwords:
        stopwords.update(extra_stopwords)

    raw_tokens = _tokenize(text)
    tokens = []
    for tok in raw_tokens:
        norm = _normalize_token(tok)
        if len(norm) < 2:
            continue
        if norm in stopwords:
            continue
        # 원래 토큰 + 의미 단위 후보 모두 보관
        for piece in [norm, *_derive_meaning_units(norm)]:
            if piece not in tokens:
                tokens.append(piece)

    counts = Counter(tokens)

    keywords: List[str] = []
    for word, _ in counts.most_common():
        if word in keywords:
            continue
        keywords.append(word)
        if len(keywords) >= top_k:
            break

    if expand_synonyms:
        base_list = list(keywords)
        for key in base_list:
            for synonym in SYNONYM_SEEDS.get(key, ()):  # type: ignore[arg-type]
                if synonym not in stopwords and synonym not in keywords:
                    keywords.append(synonym)
            for extra in _expand_domain(key):
                if extra not in stopwords and extra not in keywords:
                    keywords.append(extra)

    return keywords
