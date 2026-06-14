# Redaction & Paraphrase Rules — External Signal Ingest

본 문서는 `/ingest-external-signal` skill 이 raw payload 를 산출
파일로 변환할 때 적용하는 redaction (G21) + fact-only paraphrase (G7) 룰의
single source 다.

---

## 1. Redaction patterns (G21)

산출 본문에 다음 패턴이 노출되면 **즉시 mask**.

| 패턴 | mask 후 |
|---|---|
| `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z\|a-z]{2,}` (이메일) | `<email-redacted>` |
| `\b\+?\d{1,4}[-\s]?\d{2,4}[-\s]?\d{3,4}[-\s]?\d{3,4}\b` (전화) | `<phone-redacted>` |
| 한국 계좌번호 패턴 `\d{4,}-\d{2,}-\d{4,}` | `<account-redacted>` |
| API key 형식 (32+자 hex / base64) | `<api-key-redacted>` |
| `KIS_ACCOUNT_NUMBER` / `DART_API_KEY` / `KIS_APP_SECRET` literal 값 | `<secret-redacted>` |

`.env` 의 `SECRET_ENV_KEYS` 항목과 일치하는 값이 raw 본문에 발견되면 **즉시 abort**
+ 사용자 보고 (skill 산출 실패).

---

## 2. URL 처리

URL 은 mask 하지 않는다 — citation evidence 로 보존 (G7). 단:

- 단축 URL (bit.ly / t.co 등) 은 원본 URL 로 expand 후 저장 권장
- 추적 파라미터 (`?utm_*`, `?fbclid`, `?gclid`) 는 strip
- 로그인 페이지 / paywall 뒤 컨텐츠 URL 은 본문에 `[paywalled]` 마커 추가

---

## 3. Fact-only paraphrase (G7 + Section 3 forbidden language)

### 제거 대상

raw payload 안의 다음 표현은 paraphrase 후 본문에서 제외:

- 의견 / 권고 단어: `"should buy"`, `"strongly recommend"`, `"avoid"`, `"투자 추천"`, `"비추천"`
- 미래 가격 prediction: `"target price"`, `"price target"`, `"will reach"`, `"set to rise"`
- 가치 평가: `"undervalued"`, `"fair value"`, `"intrinsic value"` (단독 사용 시)
- alpha 주장: `"outperform"`, `"alpha"`, `"market-beating"` (sample size 미충족 시)

### 보존 대상

다음은 fact 로 분류 — 본문에 그대로 인용:

- 정량 fact: 매출 / 영업이익 / EPS / 시총 (원본 출처 명시)
- 공시 이벤트: 자사주 소각 / 분할 / 합병 / 5% 지분 변동 (DART rcept_no 포함)
- 인용 가능한 발언: CEO/CFO 발언 등 (출처 + 시점 명시, opinion 라벨)

### 변환 예시

```
DENY (원본 그대로):
  "○○지주가 강력한 자사주 소각으로 NAV 할인 좁힘이 예상되며,
   매수 추천 — 목표가 12만원."

ALLOW (paraphrased):
  "○○지주, 2026-05-09 자사주 100만주 소각 결정 공시
   (DART@2026-05-09=...). source: 한국경제 2026-05-09."
```

---

## 4. 산출 frontmatter schema

```yaml
---
schema: external-signal-v1
ticker: KR:005930        # G2 (date-ticker namespace)
source: "한국경제"        # 자유 string — citation 의 일부
type: news                # analyst-note | news | twitter | blog | user-prompt | research-report | filing
observed_at: "2026-05-11T14:30:00+09:00"
ingested_at: "2026-05-11T14:32:00+09:00"
ingested_by: ingest-external-signal
---
```

본문은 2 섹션:

- `## Fact (paraphrased, opinion-stripped)` — §3 룰 적용 후 fact-only
- `## Original (redacted)` — §1 redaction 적용 후 raw payload

---

## 5. 산출 파일 명명 (G20)

```
$EXTERNAL_SIGNAL_INTAKE_DIR/{ticker}/{date}-{seq:03d}.md
```

(= `telemetry/external_signals/{ticker}/{date}-{seq:03d}.md` — config/signals 아님.
agent 생성 append-only 증거라 ADR-0008 분류축상 telemetry 거주.)

- `{date}` — KST YYYY-MM-DD (observed_at 의 date 부분)
- `{seq}` — 같은 ticker + 같은 date 의 N 번째 ingest (001 부터 증가, zero-padded 3자리)
- 같은 seq 파일 존재 시 increment — 덮어쓰기 금지

---

## 6. 후속 cron run 에서 인용

본 ingest 산출물은 **즉시 thesis 변경 / 매매 명령에 사용되지 않는다**.
다음 day-1 cron run 의 Stage 4 thesis-auditor 가 다음 룰로 인용:

- ingest 산출의 `Fact` 섹션만 read (Original 섹션은 raw 보존 용도, 인용 금지)
- thesis 의 `entry_catalyst` / `falsifier` 본문에 인용 시 G7 형식
  `EXTERNAL_SIGNAL@{ingested_at}={source-name}` 강제
- A (정보) edge 단독 인용 시 추가 검증 강제 — `confirmation_bias_check` 필드 작성

본 절차가 깨지면 ingest 자체가 thesis 변경의 우회로가 된다 — G10 위반.
