# 병렬화 ROI 조사 — (1) per-ticker fetch 병렬화 / (2) profile 스킬 sub-agent화·병렬 init (2026-06-06)

> **성격**: [batch-fetch-and-profile-authoring-review-2026-06.md](batch-fetch-and-profile-authoring-review-2026-06.md) §5 우선순위 표의 2개 후보(per-ticker fetch 병렬화 / cold-start profile 부트스트랩)에 대한 ROI·필요성 심화 조사. read-only findings — 코드·구현 plan 없음.
> **방법**: 2개 질문을 Opus subagent 2개로 병렬 조사 → `/Users/jhan_acc/Documents/tmp/T{1,2}-*.md` (부록). 본 문서는 종합 + 핵심 주장 독립 검증("✅검증" = 작성자가 grep/read/대조로 재확인, "(보고)" = subagent 인용). rate-limit 수치는 subagent 웹 리서치 출처 인용.
> **공통 맥락**: 파이프라인 미활성 → `.cache/`·`telemetry/` 비어 universe 실 크기·fetch 부하 **미측정**. 착수형 권고는 전부 측정 선행.

---

## 0. 요약

| Task | 질문 | 판정 | 확신도 |
|---|---|---|---|
| **1** | per-ticker raw-data fetch 병렬화 ROI (+ source API 제한) | **현재 불필요 / 조건부.** 절감 대상이 사실상 cold-start 1회 wall-clock뿐(30일 캐시가 steady-state fetch ≈0 흡수). source 천장이 낮아(KIS appkey당 **초당 20건**, DART throttle) 병렬 speedup 자체가 작고, client가 **thread-safe 아님**이라 안전화(token single-flight + 공유 rate-limiter + G8 재검증) 영구 비용이 1회성 분(分) 단위 절감을 상회. | 메커니즘·KIS limit 높음 / DART 수치·N 추정 중간 |
| **2** | profile 작성 스킬 sub-agent화 + 병렬 initialize ROI | **cold-start 조건부 불필요 / 정상운영 불필요.** 병렬이 줄이는 건 phase2 LLM wall-clock 단 하나인데, cold-start 의 지배 bottleneck은 **인간 검토(phase3 수동 commit gate) + 종목별 evidence 부재**라 병렬로 못 줄인다. 토큰 절감 0, 거버넌스 이득 0(정합성은 "단건 호출"에서 오지 "병렬"에서 안 옴). **선행 권고한 순차 러너로 충분**, 병렬은 over-engineering. | 높음 |

**한 줄 종합**: 두 병렬화 모두 "줄일 수 있는 것"(fetch RTT 대기 / LLM draft wall-clock)이 1회성이거나 천장에 묶여 작은 반면, "진짜 bottleneck"(낮은 source 천장 / 인간 검토 / evidence 부재)은 병렬화가 못 건드린다. 두 경우 모두 병렬보다 **더 싸고 안전한 대안**(universe 협소화·캐시 워밍 / 순차 러너)이 우선이다.

---

## 1. 검증 요약 (작성자 독립 재확인)

- ✅ **client thread-safe 아님**: `infrastructure/dart/client.py`·`kis/client.py` 에 `threading`/`Lock`/`requests.Session`/`ThreadPool`/`asyncio`/`concurrent.futures` **0건**(grep; 유일 매칭 `KisAutoTradeBlocked` 는 무관 예외 클래스). → 병렬화는 동시성 안전화를 *새로* 구축해야 함.
- ✅ **steady-state 캐시 흡수**: `screener/config/strategies/default.yaml:15-17` `financials_ttl_days:30` / `capital_signals_ttl_days:7` / `staleness_grace_days:14`. cache hit 시 fetch skip(`screen.py:80` 가드, 선행 검증).
- ✅ **DART pacing**: `dart/client.py:124` `pause_seconds=0.05`(≈20/sec) + transient 503 retry=3 backoff(`:75-90`). KIS GET retry=0(선행 검증).
- ✅ **IP residency 차단**: `deployment-residency.md:13-17` 클라우드 IP = DART 503(WAF)/KIS timeout/KRX 403, 로컬 KR ISP만 정상 → 파이프라인은 launchd 로컬 실행.
- ✅ **스킬은 fetch 안 함**: `investment-policy-profiler/SKILL.md` frontmatter `allowed-tools: Read, Write, Bash, Grep, Glob` — **WebFetch 없음**. → profile 병렬화로 인한 DART 동시 호출 0.
- ✅ **phase3 commit = 인간 gated**: `SKILL.md:194-199` "draft 만족 시 `--commit-draft` **수동** 실행 … 어떤 결정론 단계든 **자동 호출 안 함**".
- ✅ **cold-start drift no-op**: `policy/domain/drift.py:36-37` `if prev is None: return Drift((),(),{},0.0)`.
- ✅ **신규 인프라 필요**: `.claude/agents/` **비어 있음**(커스텀 subagent 0) → 병렬 채택 시 subagent/workflow 신규 구축.
- ✅ **cold-start evidence 부재**: `config/signals/` = `macro` 디렉토리뿐(종목 dir 0).

두 보고서의 결론·확신도는 위 재확인과 일치. 이견 없음.

---

## 2. Task 1 — per-ticker fetch 병렬화

### 결론
**현재 불필요(조건부).** universe가 수백 단위로 협소화되거나 cold-start 빈도가 오르고 RTT 병목이 *측정으로* 입증되기 전까지 ROI 음수.

### #1. 절감 대상이 사실상 cold-start 1회뿐
- screener(`screen.py:76-96`)는 전 universe entry sequential 루프, cache miss 시만 per-ticker DART 호출 2종(재무 `fetch_financial_statements` 단건 + capital_signals 공시 단건, `screen.py:205,212`).
- `financials_ttl_days:30` 캐시(✅)가 steady-state fetch 를 흡수 → **대부분 날 fetch ≈ 0~소수, 일별 cron 절감분 ≈ 0초.** "Default = No Action" 정합.
- 병렬이 줄이는 건 cold-start(빈 캐시)·일괄 만료 시의 분(分) 단위 wall-clock뿐. (보고: N=300 가정 시 sequential ~5분 → 병렬 ~1–2분, 단 N 미측정.)

### #2. source 측 천장이 낮아 speedup 자체가 작다 (질문의 핵심 — rate limit)
- **KIS**: appkey당 **실전 초당 20건 / 모의 초당 5건**, 초과 시 `EGW00201`. 단위=appkey. (출처: KIS Developers 포털 + 복수 실측 블로그, 2025-10까지 유효 — T1 §출처.) → 병렬 worker 20개가 한계, 그 이상은 즉시 에러. 현 sequential 도 RTT상 초당 3–10건이라 천장 한참 아래 → 병렬화 여지는 "최대 20/sec"로 좁게 묶임.
- **DART**: 공식 약관(opendart.fss.or.kr/intro/terms.do)은 "허용량 제한 존재 + 홈페이지 게시"만 명시. 널리 인용되는 **일 20,000회·분당 ~1,000회 throttle**은 2차 출처/커뮤니티 consensus(공식 상세 수치 직접 인용 실패 — 확신도 중간). 현 `pause_seconds=0.05`(분당 ~1,200 페이스)는 이미 분당 throttle에 근접 설계 → 병렬 burst는 throttle/503을 더 자주 자극.
- **함의**: 외부 API가 per-ticker 단건이고 천장이 낮아, 병렬화의 상한 throughput이 현 sequential pacing과 큰 차이가 없다.

### #3. IP/WAF 상호작용
IP residency 차단(클라우드)과 rate-limit(요청률)은 **별개**. 로컬 KR IP라 residency는 면하나, DART 503은 `deployment-residency.md:15`상 "WAF 거부"로 WAF는 burst 패턴에도 반응 가능 → **병렬 burst가 로컬에서도 DART WAF/throttle·KIS EGW00201을 자극**. retry=3 backoff 설계 자체가 503 흡수 의도(`client.py:88` 주석). 병렬화는 IP 차단을 우회하는 게 아니라 천장에 더 빨리 부딪치게 함.

### #4. 동시성 안전화 비용 (thread-unsafe ✅)
병렬화 시 신규 필요: KIS token **single-flight**(공유 `secrets/.kis_token.json` 동시 발급 race, token rotation 무효화 위험), 공유 **token-bucket rate-limiter**(KIS 20/sec·DART throttle 전역 강제 — 이게 worker 실효 상한을 묶음), work partition, thundering-herd 완화, **G8 graceful-degrade blast radius 재검증**(현 ticker 단위 격리 → 공유 limiter 트립이 전체 영향). 이 영구 복잡도가 cold-start 1회의 분 단위 절감을 상회.

### #5. ROI / 대안 우선순위
break-even 조건(모두 충족 필요, 추정): N≥300 + cold-start 잦음(주 1회+) + 천장 미만 RTT 병목이 *측정*으로 입증 + 더 싼 대안 소진. 현재 미달.

| 대안 | 비용 | 우선순위 |
|---|---|---|
| 병렬화 | 동시성 안전화 + rate/WAF 리스크 + G8 blast radius | **낮음** |
| 캐시 만료 분산/연장 | config 변경, 신선도 trade-off | 높음(거의 무료) |
| **universe 협소화** (fetch 대상 N 자체 축소) | universe admit 룰 = 투자 로직(사냥터 폭) 결정 | 높음(근본적, 사용자 판단) |
| 점진적 캐시 워밍 (하루 N/k씩) | 소규모 스케줄러 | 중–높음 |

**권고**: 병렬화 보류. 먼저 cold-run wall-clock·실 fetch 대상 N 계측. 그래도 필요하면 병렬 *대신* "공유 limiter + single-flight + bounded(≤10) worker"만 검토(천장 초과 worker 무의미).

---

## 3. Task 2 — profile 스킬 sub-agent화 + 병렬 initialize

### 결론
**cold-start 조건부 불필요 / 정상운영 불필요.** 선행 권고한 **순차 러너로 충분**, 병렬은 over-engineering.

### #1. cold-start bottleneck 분해 — 병렬이 못 건드림
| 단계 | 성격 | cold-start 비용 | 병렬이 줄이나 |
|---|---|---|---|
| phase1 intake (`main.py:70-93`, 결정론) | 순수 변환 | 밀리초 | ✕ (무시 가능) |
| **phase2 LLM draft** (스킬) | 세션 왕복 | 세션당 수십초~분 | **○ — 유일** |
| phase3 commit (`main.py:96-137`, 결정론) | drift/version/G20 | 밀리초 | ✕ |
| **인간 검토** (✅ `SKILL.md:194-199` 수동 commit gate) | 사람 | 종목당 수분 | **✕ 병렬 불가** |
| **evidence 수집** (✅ `config/signals/` = macro뿐) | 파일 read | cold-start 대부분 빈 dir | N/A (읽을 fact 없음) |

→ 지배 bottleneck = **인간 검토 + evidence 부재**. 병렬은 phase2 wall-clock(Σ→max)만 압축. (보고 수치 직관: N=50, draft 1분/검토 3분이면 병렬 절감 ~24%, evidence 부족 보류 시 더 작아짐.)

### #2. 토큰·거버넌스 이득 0
- **토큰**: N종목 = N×(reference contract ~1150+L 재로드 + draft). 병렬·순차 공통(단건 단위라 재로드 불가피) → 절감 0, 병렬 오케스트레이터 토큰 +α.
- **거버넌스**: sub-agent=1 ticker draft면 F-10(스킬 commit 안 함)·G7(citation 격리)·G20(종목별 경로)·drift(`prev=None` no-op ✅) **무손상**. 단 그 정합성은 전부 **"단건 호출 + 종목별 경로"에서 오고 "병렬"이 기여하는 이득은 0** — 순차 러너가 동일하게 얻음.
- **fetch 충돌 없음**: 스킬 `allowed-tools`에 WebFetch 없음(✅) + policy phase1 DART 미배선(선행 검증) → profile 병렬화로 인한 DART 동시 호출 0. (단 정상운영서 phase1을 DART 자동 scan으로 배선하면 그건 phase1 결정론 문제 = Task 1 소관, 스킬 병렬화와 무관.)

### #3. 권고
**순차 러너 채택, profile 병렬화 비채택.** `.claude/agents/`가 비어(✅) 병렬 채택 시 subagent/workflow + N-agent 산출물 격리 + 부분실패 재시도를 **신규·영구 구축**해야 하는데, cold-start는 1회성·인간gated·evidence-starved라 복잡도 부채 > 1회 절감. 굳이 병렬한다면 (sub-agent=1 ticker draft만 / phase3 commit은 순차·인간gated 유지 / evidence 빈 종목은 Mode B 보류)로만 — 그래도 "있어도 무방하나 만들 이유 약함".

---

## 4. 교차 결론

- **Task 1·2 공통 패턴**: 병렬화가 줄이는 차원(fetch RTT / LLM wall-clock)이 1회성이거나 외부 천장(KIS 20/sec, 인간 검토)에 묶여 작다. 두 경우 모두 **병렬 아닌 대안이 우선** — Task 1은 universe 협소화·캐시 워밍, Task 2는 순차 러너.
- **선행 doc §5 우선순위 갱신**: 후보 2(fetch 병렬화)·4(cold-start 러너) 중 — **fetch 병렬화는 후순위로 강등**(측정 후 조건부), **cold-start는 순차 러너로 확정**(병렬 불채택). 후보 1(universe 협소화)이 두 Task의 공통 상위 레버로 재확인됨.
- **착수 전 단일 선결 측정**: 1주 운용 로그로 (a) universe 실 종목 수 N, (b) cold-run wall-clock, (c) DART/KIS 실 호출 수·EGW00201/503 빈도. 이 측정이 Task 1의 break-even·Task 2의 N 의존 결론을 모두 사실화한다.

---

## 5. 확신도 & 미확인

- **높음(구조)**: client thread-unsafe, 캐시 TTL, 스킬 no-fetch, phase3 인간gate, drift no-op, `.claude/agents/` 빈 상태 — 모두 ✅ 직접 확인.
- **높음(KIS rate limit)**: appkey당 20/sec·EGW00201 (공식 포털+복수 실측, 2025-10까지 유효).
- **중간(DART 수치)**: 일 20,000·분당 throttle은 2차 출처 consensus, 공식 상세 직접 인용 실패. DART WAF의 burst 반응(로컬 IP)은 503 관측 기반 추정.
- **중간(절대값)**: universe 실 N·cold-run wall-clock·인간 검토 시간 모두 미측정 가정. 단 결론을 좌우하는 부등식(steady-state fetch≈0 / phase2≪인간+evidence / 천장이 낮음)은 구조·설계 전제에서 robust.

---

## 부록

- T1 원본: `/Users/jhan_acc/Documents/tmp/T1-per-ticker-fetch-parallelization-roi.md` (rate-limit 출처 URL 포함)
- T2 원본: `/Users/jhan_acc/Documents/tmp/T2-profile-skill-subagent-parallel-init-roi.md`
- **부수 발견(범위 밖)**: `investment-policy-profiler/SKILL.md:39` 의 reference contract가 `domains/screener/config/methods_manifest.yaml` 을 가리키나 **실존하지 않음**(✅ 부재 확인) — resolver whitelist는 `screener/rules/resolver.py`/`methods.py`에 코드로 존재. stale 경로(본 ROI 판정과 무관, 별도 정리 후보).
