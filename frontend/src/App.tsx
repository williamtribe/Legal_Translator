import { useMemo, useState } from "react";
import "./App.css";

type Article = {
  law_id?: string;
  law_name?: string;
  article_number?: string;
  order_number?: string;
  content?: string;
  term_type_code?: string;
  term_type?: string;
  article_relation_link?: string;
};

type LegalCandidate = {
  id: string;
  name?: string | null;
  relation_code?: string | null;
  relation?: string | null;
  note?: string | null;
  legal_term_name?: string | null;
  summary?: string | null;
  articles?: Article[];
};

type DailyCandidate = {
  id: string;
  name?: string | null;
  source?: string | null;
  stem_relation_link?: string | null;
  keyword: string;
  legal_terms: LegalCandidate[];
};

type TokenBundle = {
  token: string;
  daily_terms: DailyCandidate[];
};

type TranslateResponse = {
  tokens: TokenBundle[];
  keywords?: string[];
  warnings: string[];
};

type Selection = Record<
  string, // token
  {
    dailyId?: string;
    legalId?: string;
  }
>;

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function App() {
  const [text, setText] = useState(
    "아는 형이 돈을 빌려줬는데 잠수를 탔습니다. 어떻게 해야 하나요?"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TranslateResponse | null>(null);
  const [selection, setSelection] = useState<Selection>({});
  const [activeToken, setActiveToken] = useState<string | null>(null);

  const handleTranslate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/translate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text,
          top_k: 8,
          daily_per_keyword: 5,
          legal_per_daily: 5,
        }),
      });
      if (!res.ok) {
        throw new Error(`요청 실패: ${res.status}`);
      }
      const body = (await res.json()) as TranslateResponse;
      setData(body);
      setSelection({});
      setActiveToken(body.tokens[0]?.token ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDaily = (keyword: string, dailyId: string) => {
    setSelection((prev) => {
      const prevDaily = prev[keyword]?.dailyId;
      const next = { ...prev };
      next[keyword] = {
        dailyId,
        legalId: prevDaily === dailyId ? prev[keyword]?.legalId : undefined,
      };
      return next;
    });
  };

  const handleSelectLegal = (keyword: string, legalId: string) => {
    setSelection((prev) => ({
      ...prev,
      [keyword]: {
        dailyId: prev[keyword]?.dailyId,
        legalId,
      },
    }));
  };

  const chosenLegal = useMemo(() => {
    if (!data) return [];
    const results: { token: string; daily?: DailyCandidate; legal?: LegalCandidate }[] = [];
    for (const bundle of data.tokens) {
      const sel = selection[bundle.token];
      if (!sel?.dailyId) continue;
      const daily = bundle.daily_terms.find((d) => d.id === sel.dailyId);
      const legal = daily?.legal_terms.find((l) => l.id === sel.legalId);
      results.push({ token: bundle.token, daily, legal });
    }
    return results;
  }, [data, selection]);

  return (
    <div className="app">
      <header className="header">
        <div>
          <p className="eyebrow">LEGAL TRANSLATOR</p>
          <h1>일상어 → 법률어 치환 실험</h1>
          <p className="subtitle">
            입력 문장을 단어 단위로 쪼개고, 1(일상어 조회) → 3(일상→법령 연계) → 4(법령→조문)
            순서로 후보를 보여주며 사용자가 직접 선택합니다.
          </p>
        </div>
        <button className="cta" onClick={handleTranslate} disabled={loading}>
          {loading ? "분석 중..." : "변환하기"}
        </button>
      </header>

      <section className="input-panel">
        <label htmlFor="input-text">상황 설명</label>
        <textarea
          id="input-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          placeholder="상황을 입력하세요. 예) 집주인이 보증금을 안 돌려줍니다."
        />
        {error && <div className="error">⚠️ {error}</div>}
        {data?.warnings?.length ? (
          <div className="warning">
            {data.warnings.map((w, idx) => (
              <div key={idx}>⚠️ {w}</div>
            ))}
          </div>
        ) : null}
        {data?.tokens?.length ? (
          <div className="token-pills">
            <div className="section-label">추출된 단어(클릭해서 후보 보기)</div>
            <div className="pill-row">
              {data.tokens.map((t) => (
                <button
                  key={t.token}
                  className={`pill ${activeToken === t.token ? "active" : ""}`}
                  onClick={() => setActiveToken(t.token)}
                >
                  {t.token}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="content">
        <div className="columns">
          <div className="column">
            <h2>단어별 후보</h2>
            {!data && <p className="muted">변환하기를 눌러 시작하세요.</p>}
            {data?.tokens
              .filter((b) => !activeToken || b.token === activeToken)
              .map((bundle) => (
              <div key={bundle.token} className="keyword-card">
                <div className="keyword-header">
                  <span className="chip">단어</span>
                  <span className="keyword-text">{bundle.token}</span>
                </div>
                <div className="daily-list">
                  <p className="section-label">1단계: 일상어 선택</p>
                  {bundle.daily_terms.length === 0 && (
                    <p className="muted">일상어 후보가 없습니다.</p>
                  )}
                  {bundle.daily_terms.map((daily) => {
                    const isSelected = selection[bundle.token]?.dailyId === daily.id;
                    return (
                      <label key={daily.id} className={`daily-item ${isSelected ? "selected" : ""}`}>
                        <input
                          type="radio"
                          name={`daily-${bundle.token}`}
                          value={daily.id}
                          checked={isSelected}
                          onChange={() => handleSelectDaily(bundle.token, daily.id)}
                        />
                        <div>
                          <div className="item-title">{daily.name || "(이름 없음)"}</div>
                          <div className="item-sub">source: {daily.source || "미상"}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>

                <div className="legal-list">
                  <p className="section-label">2단계: 법령어 선택</p>
                  {bundle.daily_terms
                    .find((d) => d.id === selection[bundle.token]?.dailyId)
                    ?.legal_terms.map((legal) => {
                      const isSelected = selection[bundle.token]?.legalId === legal.id;
                      return (
                        <label
                          key={legal.id}
                          className={`legal-item ${isSelected ? "selected" : ""}`}
                        >
                          <input
                            type="radio"
                            name={`legal-${bundle.token}`}
                            value={legal.id}
                            checked={isSelected}
                            onChange={() => handleSelectLegal(bundle.token, legal.id)}
                          />
                          <div className="legal-body">
                            <div className="item-title">
                              {legal.name || legal.legal_term_name || "(법령어 없음)"}
                            </div>
                            <div className="item-sub">
                              {legal.relation || "연계"} · 코드 {legal.relation_code || "-"}
                            </div>
                            {legal.summary ? (
                              <div className="summary">요약: {legal.summary}</div>
                            ) : null}
                            {legal.articles?.length ? (
                              <div className="articles">
                                {legal.articles.slice(0, 2).map((a, idx) => (
                                  <div key={idx} className="article-snippet">
                                    <div className="article-head">
                                      <span>{a.law_name || "법령명 없음"}</span>
                                      {a.article_number ? (
                                        <span className="chip subtle">조 {a.article_number}</span>
                                      ) : null}
                                    </div>
                                    <div className="article-content">
                                      {(a.content || "").slice(0, 160)}
                                      {(a.content || "").length > 160 ? "…" : ""}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="muted">관련 조문 없음</div>
                            )}
                          </div>
                        </label>
                      );
                    }) || <p className="muted">일상어를 먼저 선택하세요.</p>}
                </div>
              </div>
            ))}
          </div>

          <div className="column preview">
            <h2>선택 결과 (법률어 치환 미리보기)</h2>
            {chosenLegal.length === 0 && <p className="muted">선택된 항목이 없습니다.</p>}
            <div className="result-list">
              {chosenLegal.map(({ token, daily, legal }) => (
                <div key={token} className="result-item">
                  <div className="result-head">
                    <span className="chip">단어</span>
                    <strong>{token}</strong>
                  </div>
                  <div className="result-body">
                    <div>일상어: {daily?.name || "-"}</div>
                    <div>법령어: {legal?.name || legal?.legal_term_name || "-"}</div>
                    {legal?.summary ? <div className="summary">요약: {legal.summary}</div> : null}
                    {legal?.articles?.length ? (
                      <div className="article-preview">
                        <div className="article-head">
                          {legal.articles[0].law_name || "법령명 없음"} · 조{" "}
                          {legal.articles[0].article_number || "-"}
                        </div>
                        <div className="article-content">
                          {(legal.articles[0].content || "").slice(0, 140)}
                          {(legal.articles[0].content || "").length > 140 ? "…" : ""}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default App;
