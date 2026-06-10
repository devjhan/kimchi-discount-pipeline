# Pipeline Overview — Investment Advisory Agent Workspace

> **Last reviewed:** 2026-06-06

본 문서는 인간용 reference / index 입니다. 깊은 정의는 모두 다른 파일(AXIOMS / specs / thresholds)에 있고, 이 문서는 link 만 모읍니다. 새 fact 도입 금지.

---

## 1. 시스템 정의

본 시스템은 한국 특수상황 universe (지주사 / 우선주 / 분할 / 자사주 소각 / 행동주의 진입) 에서 institutional 이 구조적으로 진입하기 어려운 영역을 1~3년 horizon 으로 사냥하는 **personal research tool** 이다. 사용자에게 추천을 제공하되 **최종 결정 / 매매 체결은 사용자가 직접 한다**. 자동 매매 / 자동 cron 일체 없음. 자동 시그널 생성이 매일 0건이 정상 출력 — 시장에 시그널이 없는 날에 시그널을 만들어내지 않는다.

본 시스템은 **investment advice 가 아니다**.

> 각 capability 의 사용자 의도(job story)와 end-to-end trace 는 [`capabilities/`](capabilities/README.md),
> 비자명한 구조 결정의 근거(ADR)는 [`decisions/`](decisions/README.md) 참조.

---

## 2. 5 Axioms (요약 + link)

| 번호 | 이름 | 한 줄 요약 | 본문 |
|---|---|---|---|
| 1 | 생존 최우선 (Survival) | 비-에르고딕에서 기하평균 최대화. 한 번의 ruin 은 absorbing barrier — 회복 불가. fractional Kelly + drawdown circuit breaker. | [AXIOMS/ergodicity.md](AXIOMS/ergodicity.md) |
| 2 | 반증 가능성 (Falsifiability) | 모든 thesis 는 time-cap / metric-trigger / event-trigger 카테고리의 구체적 falsifier 를 갖는다. vague falsifier reject. | [AXIOMS/falsifiability.md](AXIOMS/falsifiability.md) |
| 3 | 엣지 원천 명시 (Edge Source) | "왜 시장이 틀렸는가" 에 답해야 thesis 성립. 4 분류 (A 정보 / B 행동 / C 구조 / D 시간). 본 시스템 본질은 C+D. | [AXIOMS/edge-source.md](AXIOMS/edge-source.md) |
| 4 | 비대칭 손익비 (Asymmetry) | downside_floor / upside_ceiling 비율 ≥ 2 강제. 누락 시 reject. barbell portfolio. | [AXIOMS/asymmetry.md](AXIOMS/asymmetry.md) |
| 5 | 통계적 정직성 (Statistical Honesty) | sample size N 별 허용 표현 hard rule (N<10 alpha claim 금지, N<30 directional only, N<100 t-stat p<0.10 필요). | [AXIOMS/statistical-honesty.md](AXIOMS/statistical-honesty.md) |

---

## 3. 파이프라인 흐름도

```
[positions_sync]            → KIS read-only 계좌 sync (balance/cash/PnL)
            ↓
[portfolio_state_derive]    → drawdown / cash% derive (sizing 의 input)
            ↓
[Stage 0a] breadth_fetch  → SPX 200d 비율 (Yahoo public chart)
            ↓
[Stage 0]  macro_regime  → cash band, total exposure budget
            ↓
[Stage 1]  universe       → A (특수상황) 후보군 (+ 1b NAV calc + 1c pref spread)
            ↓
[Stage 2]  quality_filter → C ∩ A (보유 가능한 후보군) (+ 2a fin_fetch)
            ↓
[Stage 3]  catalyst_scan  → trigger 발생 종목 (+ 3a index deletion + 3b earnings panic)
            ↓
[Stage 4]  thesis_gate    → 5필드 thesis 강제 (skill — invest-stage4-thesis-auditor)
            ↓
[Stage 5]  sizing         → fractional Kelly + asymmetry budget
            ↓
[Stage 5a] thesis_sync    → 04-thesis-candidates → positions/{ticker}/thesis.json 결정론 파생
            ↓
[Stage 5b] falsifier_proximity     → 보유 포지션 falsifier 근접도
[Stage 5c] event_falsifier_linker  → event_trigger falsifier × Stage 3 catalyst join
[Stage 5d] thesis_expiry_monitor   → time_horizon_months 추적 (T-90 / T-30 / T-0 / T+30)
            ↓
[Stage 6]  brief_author   → 사람용 markdown brief (skill — invest-stage6-brief-author)
```

---

## 4. Stage 별 책임 표

| Stage | 책임 | 입력 | 출력 | gate (예정) |
|---|---|---|---|---|
| 0 | regime classify (FRED 기반) | `$THRESHOLDS_PATH` + FRED API | `$TRAIL_TODAY/00-macro-regime.json` | secret redact |
| 1 | universe build (DART+KIS) | DART filings + KIS company list | `$TRAIL_TODAY/01-universe.json` | path guard |
| 2 | quality gate (ROIC/debt/FCF) | `$TRAIL_TODAY/01-universe.json` + DART filings | `$TRAIL_TODAY/02-quality-filter.json` + `02-quality-lens.json` | path guard |
| 3 | catalyst scan (corporate actions) | `$TRAIL_TODAY/02-*` + DART events | `$TRAIL_TODAY/03-catalyst-events.json` | path guard |
| 4 | thesis discipline (skill) | `$TRAIL_TODAY/03-*` | `$TRAIL_TODAY/04-thesis-candidates.json` | falsifier + asymmetry validators |
| 5 | sizing (Kelly + asymmetry) | `$TRAIL_TODAY/04-*` + `$THRESHOLDS_PATH` + `$POSITIONS_DIR/_derived-{date}.json` | `$TRAIL_TODAY/05-sizing-recommendation.json` | sample size gate |
| 5a | thesis sync (결정론 파생) | `$TRAIL_TODAY/04-thesis-candidates.json` | `$POSITIONS_DIR/{ticker}/thesis.json` | G6 deterministic |
| 5b | falsifier proximity (보유 포지션) | `$POSITIONS_DIR/{ticker}/thesis.json` | `$TRAIL_TODAY/05b-falsifier-proximity.json` + `$POSITIONS_DIR/{ticker}/drift-{date}.md` | G6 deterministic |
| 5c | event falsifier linker | `$POSITIONS_DIR/{ticker}/thesis.json` + `$TRAIL_TODAY/03-*` | `$TRAIL_TODAY/event-trigger-status-{date}.json` | G6 deterministic |
| 5d | thesis expiry monitor | `$POSITIONS_DIR/{ticker}/thesis.json` | `$TRAIL_TODAY/05d-thesis-expiry.json` + `$POSITIONS_DIR/{ticker}/expiry-{date}.md` | G6 deterministic, multi-tier alert |
| 6 | brief synth (skill) | `$TRAIL_TODAY/00..05d` | `$TRAIL_TODAY/daily-brief.md` | citation gate, forbidden language |

가드 hook 의 상세 매핑은 [.claude/hooks/AGENTS.md](../.claude/hooks/AGENTS.md) 참조.

### 4b. Completeness Gate (Stage 1 universe → Stage 2 screener)

universe(Stage 1 *enrich*)↔screener(Stage 2 *cutoff*) 경계는 `01-universe.json`
단방향 파일 핸드오프로 깨끗하다. 두 도메인은 IO shape·타이밍·카디널리티 차이로
정당하게 분리돼 있고, 통합 관심사는 `EnrichCutoffProfile` (policy 산출 계약)로 hoist 됐다.

**Completeness Gate** 는 그 계약에서 비롯한 **의도된 cross-domain 결합**이다:

- screener 의 cutoff 단계(`domains/screener/application/screen.py` Step 4.2)는 자기 절반
  (`cutoff_rules`) 외에 universe 의 `required_enrichments` 도 읽어, "enrich 가 무엇을
  했어야 하나" 대비 입력 완전성을 판단한다.
- 필수 enrichment 가 누락된 종목은 `verdict="caution"` 으로 분기(배치 미중단, 사람
  재검토) — citations 보유해도 면제 아님.
- 프로파일 없음 → 게이트 skip (전환기 default_rule 진행, Default No-Action).

이는 `EnrichCutoffProfile` 이 enrich+cutoff 를 **한 정책 단위**로 묶은 데서 오는
결합으로, 모듈 경계 위반이 아니라 명시적 입력-완전성 게이트다. (대안 — universe 가
산출물에 "enrichment-complete 플래그"를 박아 screener 가 universe 지시문을 몰라도 되게
하는 방식 — 은 profile_registry cutover 후 재평가한다.)

**ISP 결정 (shared contract 의 fat 의존).** universe 는 사실상 `required_enrichments`
만, screener 는 `cutoff_rules` 만 쓰지만 둘 다 `EnrichCutoffProfile` *전체* 에 의존한다.
이를 universe-view / screener-view 로 쪼개지 **않는다** — 프로파일은 enrich+cutoff 를
한 호흡으로 정의하는 **단일 정책 단위**이고, 통째 의존이 그 의도를 정직하게 반영한다.
(serde 분할 비용 > ISP 이득, 특히 cutover 대기 중. `domains/_shared/profile_registry/schema.py` 참조. 결정 근거·대안: [ADR-0006](decisions/0006-fat-contract-isp.md).)

---

## 5. Manual invoke 명령

자동 스케줄의 canonical 경로는 **launchd** (`infrastructure/scheduling/install.sh` 단일 통로) 다.
현재 `daily_pipeline` 은 `schedules.yaml` 에서 `enabled: false` 라 비활성 — 아래는 수동 invoke.
cloud (`/schedule`) · scheduled-tasks 경로는 **deprecated** (KIS/DART/KRX IP 차단 — `deployment-residency.md`).

```bash
# 전체 파이프라인 (Stage 0~6 순차)
bash applications/daily_pipeline.sh --date $(date +%Y-%m-%d)

# 또는 stage 별:
python -m domains.macro.main                   --date YYYY-MM-DD
python -m domains.universe.main                --date YYYY-MM-DD
python -m domains.screener.main                --date YYYY-MM-DD
# (Stage 1b NAV / 1c PrefSpread 는 universe.main 의 enricher 로 통합, 별도 실행 불필요)
python -m domains.catalyst.main                --date YYYY-MM-DD
# Stage 4 = skill (invest-stage4-thesis-auditor) — agent 가 호출
python -m domains.risk_engine.sizing            --date YYYY-MM-DD
# Stage 6 = skill (invest-stage6-brief-author)  — agent 가 호출

# Audit (별도 일정) — 일별 결정론 갱신 엔진 (F-6). init 은 init_shadow_state (1회).
python -m domains.audit_integrity.main --date YYYY-MM-DD
```

orchestrator 스크립트는 `applications/` 에 있으며 (`run_daily_local.sh` / `daily_pipeline.sh`), 실제 crontab 등록 없이 launchd 또는 수동 invoke 로만 실행된다.

---

## 6. 경로 해석 (path helpers)

중앙 topology alias SSoT 는 제거됐다. 경로는 도메인 코드가 `infrastructure/_common/utils.py`
의 path helper (`trail_dir()` / `audit_dir()` / `positions_dir()` / `profiles_dir()` 등) 로 직접
계산한다. 각 helper 는 대응 env var (`$TRAIL_TODAY` / `$AUDIT_DIR` / `$POSITIONS_DIR` 등) 가
set 이면 우선 사용 — 테스트 / cron / cloud override 용. BC 도메인은 `_boundary.py` 의
`resolve_path()` / `resolve_trail_dir()` 단일 게이트를 통과한다.

본 문서·SKILL 의 `$ALIAS` 표기는 readable shorthand 이며, 그 실제 경로 매핑은
.agents/skills/contract/bootstrap.md` 의 "경로 표기" 레전드에 정의돼 있다.

---

## 7. Default = No Action 재확인

- 대부분의 manual run 에서 새 후보 0, 보유 포지션 thesis-breaking event 0, action required = None 이 정상.
- 매일 시그널이 나오면 그것은 시그널 노이즈를 만드는 시스템.
- 일주일 변화 0 이면 정상 신호.
- 현금 100% 유지가 valid output.

Forbidden language 표 + G1-G22 hard guard 정의는 [AGENTS.md](../AGENTS.md) Hard Guards.

외부 의견(뉴스 / 트윗 / 리포트 / 사용자 prompt) 은 명시적 `/ingest-external-signal` 명령으로만 ingest. prompt 본문에 직접 붙여넣어 thesis 변경 요청 금지.

---

## 관련 문서

- [AGENTS.md](../AGENTS.md) — agent 컨텍스트 (canonical)
- [governance/AXIOMS/](AXIOMS/) — 5 철학 본문
- [governance/capabilities/](capabilities/README.md) — capability map + job story (의도 layer)
- [governance/decisions/](decisions/README.md) — ADR register (구조 결정 영구 ledger)
- [AGENTS.md](../AGENTS.md) — G1-G22 hard guard / forbidden language / output envelope
- [governance/thresholds.yaml](thresholds.yaml) — 정량 임계값 SSOT
- 경로 해석 — `infrastructure/_common/utils.py` 의 path helper (중앙 topology alias SSoT 는 제거됨, 위 §6 참조)
- [governance/procedures/](procedures/) — runtime / manual invoke 절차
