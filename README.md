만들게 된 배경 
https://www.notion.so/2025-2b82b327b6bb8034b68cd11ef6a36566?source=copy_link

일반인의 말을 법률가의 말로 통역해주는 AI
이를 위해 law.go.kr (법제처)의 8개 API 활용
0, 법령용어 조회,
1, 일상용어 조회,
2, 법령용어-일상용어 연계 조회,
3, 일상용어-법령용어 연계 조회,
4, 법령용어–조문 연계 조회,
5, 조문–법령용어 연계 조회,
6, 법령 용어 목록 조회,
7, 현행법령(시행일) 본문 조항호목 조회

Backend:
promt: txt, 사용자가 궁금한 점 질문 또는 현재 자신이 겪고 있는 상황 설명
prompt에서 단어들 파싱, 단어 단위로 API에 입력

해당 API 가지고 질문이 들어오면 해당 질문에서 사용된 단어들을 이용해서 연관 조문들을 찾는다.
1, 일상용어 조회,
3, 일상용어-법령용어 연계 조회,
4, 법령용어–조문 연계 조회,
7, 현행법령(시행일) 본문 조항호목 조회
lawgokrAPI.xlsx를 이용해 함수목록 및 구조 빌드

기술
lawgokrAPI.xlsx: 한국법제처 API들 중 필요한것과 그들의 request API, 그리고 request형식이 sheet들에 있다.
crawler.py: 한국 법제처 API 이용해 법률정보를 가져온다. 0부터 7중 하나를 고르면 그 DB가 업데이트 된다.
embedder.py: 

한국 법제처의 API이용해 RAG DB 구축

Relation-DB를 이용해 RAG
Table과 기능
LEGAL_KEYWORDS: 법제처에 있는 모든 법률용어 (PK id(=법령용어ID), name(법령용어명), note(법령용어상세검색 링크 /LSW/lsTrmInfoR...), dict_kind_code(사전구분코드), law_kind_code(법령종류코드).)
LEGAL_TO_DAILY: 법제처에 있는 모든 법률용어와 일상용어의 관계 (PK id)
DAILY_KEYWORDS: 법제처에서 관계가 있는 법률용어가 존재하는 일상용어가 있는 
meta_data: 모든 테이블의 열들의 값이 의미하는 바 (PK table_name (=표 이름), column설명)

## 정규화된 RDB 설계 (Supabase 기준)
- `law_term`(=LEGAL_KEYWORDS): PK `id`(법령용어ID), `name`, `note`, `detail_link`(DRF JSON 조회 URL), `created_at`, `updated_at`.
- 코드 마스터: `dict_kind`(사전구분코드), `law_kind`(법령종류코드) + 브리지 `law_term_dict_kind`, `law_term_law_kind`로 콤마 구분 복수 코드 대응.
- `daily_term`(=DAILY_KEYWORDS): 일상용어 ID/명.
- `term_relation`(=LEGAL_TO_DAILY): FK `legal_id` → `law_term`, FK `daily_id` → `daily_term`, `relation_code`, `relation`, `created_at` (PK: `legal_id, daily_id, relation_code`).
- `meta_data`: `key`(예: table_name), `value`(jsonb), `updated_at`로 컬럼 의미, 수집 버전, totalCnt 등을 기록.

## 법제처 API 개요 (lawgokrAPI.xlsx 요약)
- 0 `lstrmAI`: 법령용어 조회 확장. 요청 `query`, `display`, `page`; 응답 키워드/검색결과개수/페이지.
- 1 `dlytrm`: 일상용어 조회. 요청 `query`, `display`, `page`.
- 2 `lstrmRlt`: 법령→일상 연계. `query` 또는 `MST`(법령용어ID) 필수. 응답에 법령용어 id/명, 연계 일상용어 리스트.
- 3 `dlytrmRlt`: 일상→법령 연계. `query` 또는 `MST`(일상용어ID) 필수. 응답에 일상용어명, 출처, 연계 법령용어.
- 4 `lstrmRltJo`: 법령용어–조문 연계. `query` 필수.
- 5 `joRltLstrm`: 조문–법령용어 연계. `query`(법령명) 또는 `ID`(법령ID) 필수.
- 6 `lstrm`: 법령용어 목록 조회(가나다/검색). `query`, `gana`, `display`, `page`, `sort`, `regDt`, `dicKndCd` 등.
- 7 `eflawjosub`: 현행법령(시행일) 본문 조항/호/목 조회. `ID`(법령ID) 또는 `MST`(lsi_seq) 필수.

## 수집·적재 흐름
- 법령용어: `scripts/fetch_lstrm_rlt.py lstrm --strategy both ...` 실행 → JSONL 저장 → Supabase RPC `upsert_law_terms`로 `law_term`/브리지 upsert.
- 법령↔일상 관계: `scripts/fetch_lstrm_rlt.py relations ...` 실행 → `daily_term`, `term_relation` 적재.
- 메타 관리: 각 수집 배치에서 totalCnt, strategy, 수집일 등을 `meta_data`에 기록해 재현성과 누락 체크.
