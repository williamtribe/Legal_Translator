from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pipeline import run_pipeline

app = FastAPI(title="Legal Translator", version="0.2.0")

# Dev CORS 허용 (필요 시 제한)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TranslateRequest(BaseModel):
    text: str = Field(..., description="사용자의 상황 설명 문장")
    top_k: int = Field(8, ge=1, le=30, description="추출할 키워드 수")
    daily_per_keyword: int = Field(3, ge=1, le=30, description="키워드당 일상용어 조회 수")
    legal_per_daily: int = Field(5, ge=1, le=50, description="일상용어당 연결할 법령용어 수")


class Article(BaseModel):
    law_id: str | None = None
    law_name: str | None = None
    article_number: str | None = None
    order_number: str | None = None
    content: str | None = None
    term_type_code: str | None = None
    term_type: str | None = None
    article_relation_link: str | None = None


class LegalCandidate(BaseModel):
    id: str
    name: str | None = None
    relation_code: str | None = None
    relation: str | None = None
    note: str | None = None
    legal_term_name: str | None = None
    summary: str | None = None
    articles: list[Article] = []


class DailyCandidate(BaseModel):
    id: str
    name: str | None = None
    source: str | None = None
    stem_relation_link: str | None = None
    keyword: str
    legal_terms: list[LegalCandidate] = []


class KeywordBundle(BaseModel):
    token: str
    daily_terms: list[DailyCandidate] = []


class TranslateResponse(BaseModel):
    tokens: list[KeywordBundle]
    keywords: list[str] | None = None  # backwards compatibility
    warnings: list[str] = []


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/translate", response_model=TranslateResponse)
async def translate(request: TranslateRequest):
    try:
        result = run_pipeline(
            request.text,
            top_k=request.top_k,
            daily_per_keyword=request.daily_per_keyword,
            legal_per_daily=request.legal_per_daily,
        )
    except Exception as exc:  # pragma: no cover - network/IO paths
        raise HTTPException(status_code=500, detail=str(exc))

    return result
