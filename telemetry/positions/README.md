# `telemetry/positions/` — 보유 포지션 스토어 계약 (SSoT)

`schema: positions-store-contract-v1`
`last_updated: 2026-06-03`

이 디렉토리는 **보유 포지션의 cross-day state** 를 담는 **multi-owner 데이터 스토어**다.
경로 shorthand 는 `$POSITIONS_DIR` (= `positions_dir()` / 기본 `telemetry/positions/`).

> 본 README 가 스토어 shape 의 **단일 계약(SSoT)** 이다. 이전엔 계약이
> `positions_sync` / `portfolio_state_derive` docstring + stage4 skill docs 에 산재해
> `ls` 만으론 무엇이 들어가야 하는지 알 수 없었다. (architecture review F-5a)

---

## 1. 왜 risk_engine 안이 아니라 telemetry 인가

- **code↔data 불변식**: 저장소 전역에서 코드(`domains/`)와 데이터(`telemetry/`)는 분리된다.
  positions 는 데이터이므로 `telemetry/` 에 있고, 이를 다루는 코드는 `domains/risk_engine/` 에 있다.
- **multi-owner**: positions 는 risk_engine 사유물이 아니다.
  - 핵심 객체 `thesis` (falsifier spec) 는 **stage4-thesis-auditor skill + 사용자**가 저작한다.
  - risk_engine 은 `balance` / `_summary` / `_derived` / `drift` / `expiry` 같은 **기계적 파생물**만 쓴다.
  - 읽기는 risk_engine + brief/audit skill 로 cross-cutting.
  → 그래서 risk_engine 패키지 *안으로* 옮기는 것은 안티패턴(스킬이 패키지 내부로 reach-in).

---

## 2. 스토어 레이아웃

```
$POSITIONS_DIR/
├── _summary-{date}.json      계좌 일별 스냅샷 (총자산/현금/보유수/실현손익)
│      schema: investment-positions-sync-v1
│      writer: domains/risk_engine/positions_sync.py  (KIS read-only sync)
│
├── _derived-{date}.json      파생 포트폴리오 state (drawdown% / cash%)
│      schema: investment-portfolio-derived-v1
│      writer: domains/risk_engine/portfolio_state_derive.py
│      reader: domains/risk_engine/sizing.py (portfolio.yaml 값이 null 일 때 fallback)
│
└── {ticker_dir}/             종목 디렉토리 (콜론 sanitize: KR:003550 → "KR_003550")
    ├── balance-{date}.json    종목별 보유 스냅샷 (수량/평단/평가/매도가능)
    │      schema: investment-positions-sync-v1-perticker
    │      writer: domains/risk_engine/positions_sync.py
    │
    ├── thesis.json            ← MACHINE STATE — falsifier spec (아래 §3)
    │      reader: falsifier_proximity.py / thesis_expiry_monitor.py / event_falsifier_linker.py
    │      writer: domains/risk_engine/thesis_sync.py (Stage 5a — §4)
    │
    ├── thesis.md              ← NARRATIVE — 사람용 thesis 본문 (아래 §3)
    │      author: investment-stage4-thesis-auditor skill / 사용자 (명시 명령 시에만)
    │
    ├── drift-{date}.md        falsifier proximity 리포트 (반증 근접도)
    │      writer: domains/risk_engine/falsifier_proximity.py
    │
    └── expiry-{date}.md       thesis time-horizon 만료 모니터
           writer: domains/risk_engine/thesis_expiry_monitor.py
```

공통 규칙:
- **G20 (덮어쓰기 금지)**: 모든 writer 는 `write_output_safely` 경유 — 충돌 시 `.{N}.json` suffix.
  날짜 박힌 파일(`*-{date}.*`)은 일별 이력 보존.
- **G7 (citation)**: 모든 잔고/현금/평가 숫자는 source citation 보유 (`KIS@<ts>=<value>`, `POSITIONS@<date>=...`).
- JSON 산출물은 `base_report_envelope` 래핑(`schema`/`generated_at`/`date` + `payload`).

---

## 3. `thesis.json` (machine state) vs `thesis.md` (narrative) — 역할 확정

한 포지션의 thesis 는 **두 표현**으로 나뉜다. 둘은 같은 thesis 의 서로 다른 면이다:

| | `thesis.json` | `thesis.md` |
|---|---|---|
| 성격 | **기계 판독 state** (falsifier spec) | **사람용 narrative** |
| 저자 | `thesis_sync.py` (Stage 5a, 04-thesis-candidates 파생) / 사용자 | stage4-thesis-auditor skill / 사용자 (명시 명령 시) |
| 소비자 | risk_engine Python (일별 monitoring) | 사람 (검토) + stage4 skill (amendment 판단 입력) |
| 변경 빈도 | falsifier 도달/amendment 시 | thesis 재작성 시 |

### `thesis.json` 스키마 (risk_engine 리더가 기대하는 shape)

`falsifier_proximity.py` / `thesis_expiry_monitor.py` / `event_falsifier_linker.py` 가
`{ticker}/thesis.json` 을 load 한다. `status != "open"` 이면 skip. 기대 shape:

```json
{
  "ticker": "KR:003550",
  "name": "LG",
  "entry_date": "2026-01-15",
  "entry_price_krw": 84000,
  "status": "open",
  "thesis": {
    "entry_catalyst": "...",
    "falsifier": {
      "category": "time_cap | metric_trigger | event_trigger",
      "spec": { }
    },
    "time_horizon_months": 18,
    "edge_source": ["C", "D"],
    "asymmetry_score": { }
  }
}
```

`thesis.thesis` 의 5 필드(`entry_catalyst` / `falsifier` / `time_horizon_months` /
`edge_source` / `asymmetry_score`)는 stage4 thesis-auditor 가 `04-thesis-candidates.json`
으로 산출하는 thesis schema 와 동형이다 (falsifiability / edge-source / asymmetry 축).

### `thesis.md`

stage4-thesis-auditor 가 accepted 후보의 thesis 본문을 **사용자 명시 명령 시에만**
`{ticker}/thesis.md` 로 write 한다. `thesis.md` 존재 여부로 thesis_kind(new_entry vs
amendment)를 분류한다. risk_engine Python 은 `thesis.md` 를 읽지 않는다.

---

## 4. `thesis.json` writer — Stage 5a Thesis Sync (gap 해소, F-5b)

`thesis.json` (machine state) 은 **구조화된** `04-thesis-candidates.json` 에서 결정론
파생된다 (narrative `thesis.md` 의 LLM markdown 파싱이 아니라 — fragility 회피).

- **writer**: `domains/risk_engine/thesis_sync.py` (Stage 5a). `daily_pipeline.sh` 의
  post-stage4 phase 에서 5b/5c/5d monitor **앞**에 실행 (갓 파생된 thesis.json 을 보도록).
- **schema bridge**: stage4 falsifier `{categories[], items[]}` → reader 단일 `{category, spec}`
  로 투영(primary=items[0], threshold→target_value, edge_source.primary→list). 다중 falsifier
  는 primary 만 투영 + warning.
- **불변식**: `verdict=="accepted"` AND `thesis_kind=="new_entry"` 후보만 write.
  amendment / needs_user_decision / 보유 포지션은 절대 auto-write 안 함(user-gated).
  **멱등** — 기존 `thesis.json` 존재 시 clobber 금지(`entry_date` reset / `.{N}.json` spam 방지).
- **G7**: asymmetry `source_citation` 을 `_provenance.citations` 로 carry.
- **store**: 스키마/serde/접근은 `domains/_shared/positions_store/` 가 형식화
  (`profile_registry` 와 동형: schema + serde + injected-writer). risk_engine 은
  `_boundary.py` 게이트(`positions_store()` / `commit_thesis()`)로만 접근.

---

## 5. 접근 패턴 (F-5b 형식화 완료)

- positions 스키마/접근은 `domains/_shared/positions_store/` 가 소유한다
  (`profile_registry` 와 동형: `schema` + `serde` + injected-writer `store`).
  `infrastructure` import 0 — root·writer 는 caller 가 주입.
- risk_engine 은 `domains/risk_engine/_boundary.py` 단일 게이트로만 외부에 접근한다
  (path / KIS read-only / positions_store / `_derived` read). 3 monitor 의 중복 로더는
  `PositionsStore.load_open_raw` 로 단일화됨.
