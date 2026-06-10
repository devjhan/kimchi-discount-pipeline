# Audit — runtime-policy + KisAccountPort (in-BC ViolationLog 없음)

## 모델 차이 (vs universe)

risk_engine 은 **`audit/` 서브패키지가 없다** (universe 의 `audit/{invariants,log,violation,
citation}.py` 없음). in-BC `ViolationLog` / `rule_name` / invariant JSONL **없음**.
risk_engine 산출물의 audit 는 외부 read-only skill (`investment-audit-process` /
`investment-audit-outcome`, `$AUDIT_DIR` 에 기록) 이 수행. 본 BC 는 대신 **정적/타입 guard**
로 안전을 강제한다 — 이것이 risk_engine audit 의 본질.

## G9 (자동매매 차단) — 4중 구조적 guard

risk_engine 은 자본 안전의 마지막 보루. 자동 매매 체결은 4겹으로 차단:

1. **`governance/runtime-policy.yaml`** (G9 정적 enforcement)
   - `agent.block_auto_trade: true` (G9a, "변경 금지")
   - `kis.read_only_account.enabled: false` default + `allowed_tr_ids` whitelist (G9b)
   - `kis.read_only_account.forbidden_tr_ids` — 모든 주문 TR_ID blocklist (G9c)
2. **`infrastructure/kis/client`** — 주문 TR_ID 호출 시 `KisAutoTradeBlocked` raise
3. **`governance/runtime-policy.yaml`** Bash deny pattern
4. **`ports/kis_account.KisAccountPort`** — read 6 메서드만 노출, 매매가 *type 으로 표현 불가*
   (F-17, 4번째 구조적 guard)

`positions_sync.main` 은 `KisAutoTradeBlocked` 를 절대 graceful 처리하지 않고 **exit 2 fail-loud**.

## 적용 G-guard

| G | 내용 | risk_engine 적용 |
|---|---|---|
| G5 | asymmetry<2 → reject/half-cap | `domain/sizing.size_one` |
| G6 | 정량 계산 Python 단독, LLM 계산 금지 | 모든 `domain/` 산식 — sizing/proximity/expiry/portfolio_state |
| G7 | 숫자는 `{source}@{ISO}={value}` citation | `format_citation` (예: `KIS@{ts}=...`) 전 stage |
| G8 | helper 미fetch 데이터 LLM 메모리 채움 금지 | graceful `skip_reason` / warning |
| **G9 / G9a/b/c** | 자율/매매 차단 — **본 BC 핵심** | 위 4중 guard (`positions_sync` / `_boundary` / `ports/`) |
| G12 | user portfolio context 없으면 size 보류 | `application/sizing` (`01-sizing.md`) |
| G16 | 단일 25% cap + 합산 Kelly ≤ 0.5 | `per_position.max_pct` / `apply_portfolio_kelly_cap` |
| G17 | drawdown −15% → 전 size 절반 | `drawdown_brake.threshold_pct` + `size_one` brake |
| G18 | cash% < regime `cash_band[0]` 금지 | `application/sizing` cash-band block |
| G20 | audit/state overwrite 금지, date 보존 | `write_output_safely` (`.{N}` suffix) |
| G21 | secret (key/token/계좌번호) 노출 금지 | `secret_safe_log`; 계좌번호 mask |

## G7 / G20 / G21 inline 강제

- **G7**: 모든 산출 숫자는 `_boundary.format_citation` 으로 citation 부착
- **G20**: 같은 날 재실행은 overwrite 아닌 `.{N}.json` / `.{N}.md` (`_write_drift_md` /
  `_write_expiry_md` / `write_output_safely`)
- **G21**: `secret_safe_log` 로 warning redact, KIS 계좌번호 mask

## 향후

- application → port 전환 (ADR-0005) 시, port contract test 가 추가 정적 guard 역할
- (선택) in-BC invariant (예: sizing cap 사후 검증) JSONL 도입 — 현재는 정적 guard 로 충분
