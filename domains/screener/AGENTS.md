# domains/screener

Stage 2 quality filter + 향후 백테스트 인프라. **DDD modular monolith bounded context.**

기존 `domains/alpha_factory/` 의 Stage 2 3파일 (`quality_filter.py` / `stage2_fin_fetch.py` / `stage2_roic_peer_build.py`) 을 데이터 드리븐 패키지로 흡수.

## 사용

```bash
# Production
python -m domains.screener.main --date 2026-05-15 --strategy default

# Dry-run (DART fetch skip, cache miss → unknown)
python -m domains.screener.main --dry-run --date 2026-05-15
```

## 4 핵심 Anchor

`.guidelines/00-overview.md` 참조.

1. `RuleFactory.build_strategy` 단일 진입점
2. `resolver.resolve_metric` 화이트리스트 (dynamic eval 금지)
3. `clock.can_see` IO 한정
4. `_boundary.py` 단일 외부 게이트

## 외부 연결점

### Inbound (read)

| # | 외부 객체 | 어댑터 | 변환 |
|---|---|---|---|
| 1 | DART API (infrastructure.dart.client) | `io/dart_adapter.py` (via `_boundary.dart_*`) | `FilingMetric` list + capital_signals events |
| 2 | `$TRAIL_TODAY/01-universe.json` | `io/universe_loader.py` | `UniverseEntry` tuple |
| 3 | KRX holiday data | `time/calendar.py` (via `_boundary.is_trading_day`) | `bool` |
| 4 | System clock | `time/clock.py` | `AsOfClock` |
| 5 | 경로 (path helper) | `_boundary.resolve_path` / `profiles_root` | `Path` |

### Outbound (write)

| # | 외부 객체 | 어댑터 | 형식 |
|---|---|---|---|
| 1 | `$TRAIL_TODAY/02-quality-filter.json` | `io/trail_writer.py` | D-Q-2 envelope + verdicts |
| 2 | `$TRAIL_TODAY/02-fin-fetch.json` (선택) | `io/trail_writer.py` | D-Q-2 envelope |
| 3 | stdout handoff 1줄 | `_boundary.emit_summary` | D-Q-6 `[stage2-screener] ...` |
| 4 | violation log | `audit/log.py` | JSONL append-only |
| 5 | live cache | `io/financial_cache.LiveFinancialCache` | v4 schema |

### Downstream consumer (계약 보존)

| Consumer | 위치 | Read | 보장 |
|---|---|---|---|
| Stage 3 catalyst scan | `domains/catalyst/main.py` | `verdicts[].verdict == "pass"` | path / schema name 보존 |
| Stage 4 thesis-auditor | skill | 산출 존재 + verdict | envelope 보존 |
| Stage 6 brief-author | skill | `verdicts[]` 인용 | citation G7 보존 |
| Quality lens | skill `investment-stage2-quality-lens` | `verdict == "pass"` 만 | verdict 필드 보존 |
| Audit shadow | `domains.audit_integrity.main` 결정론 엔진 | `verdicts[]` (tier_3 pool) | append-only |

### Shared kernel (cross-cutting, 재구현 금지)

`infrastructure._common.utils` 의 `KST` / `format_citation` / `emit_summary_line` / `write_output_safely` / `base_report_envelope` / `trail_dir` / `audit_dir` / `profiles_dir` / `is_trading_day` + `infrastructure.dart.client` — `_boundary.py` 가 단일 export.

## Ports & Adapters (feature-first hexagonal)

`_boundary.py` 는 *fat god-facade* (5~7 무관 concern bag) 에서 **typed adapter factory** 로 진화 중이다. 외부 의존을 narrow `typing.Protocol` **port** 로 선언하고, `_boundary` 가 concrete **adapter** 를 구성하며, composition root (`main.py`) 가 순수 use-case 에 주입한다. 선례 = `domains/policy/ports/llm.py` (PolicyEngine) → `infrastructure/llm` (F-13/D-CORE-7).

| 요소 | 위치 | D-CORE-4 | 비고 |
|---|---|---|---|
| **Port (Protocol)** — cross-cutting | `domains/_shared/ports/*.py` | 안전 (순수 typing, infra import 0) | ≥2 BC 공유 (CitationPort / ClockPort / …) |
| **Port (Protocol)** — BC-local | `domains/<bc>/ports/*.py` | 안전 | 1 BC 전용 (Config 등) |
| **Adapter (impl)** | `_boundary.py` (유일 infra-import 파일, 게이트 유지) | infra import (게이트만 허용) | factory 함수 `xxx_adapter() -> XxxPort` |
| **Composition root** | `main.py` | `_boundary`(factory)+`ports`(type)+`application`(pure) | 어댑터를 use-case 에 주입 |

**불변식**: `application/` · `domain/` 은 `_boundary` import 0 (port Protocol 에만 의존). 게이트 *삭제* 금지 — D-CORE-4 강제, `_boundary` 는 유일 infra-import 파일로 잔류.

**현 적용 (Phase 0):**
- `CitationPort` (`domains/_shared/ports/citation.py`) ← `_boundary.citation_adapter()` 가 impl 구성, `main → run_screen → _refetch_into_cache → io/dart_adapter` 로 주입. `io/dart_adapter` 는 `_boundary.format_citation` free fn 직접 호출 대신 주입된 port 사용.
- `ClockPort` (`domains/_shared/ports/clock.py`) — `AsOfClock` 가 구조적으로 만족하는 명명 port (형식화만, wiring 후속).

## 디렉토리 구조

```
domains/screener/
├── AGENTS.md                # (CLAUDE.md → AGENTS.md symlink, gitignored)
├── main.py
├── _boundary.py             # 외부 의존 단일 게이트
├── errors.py
├── schemas.py
├── time/                    # AsOfClock + KRX calendar wrapper
├── domain/                  # TickerSnapshot, FilingMetric, RuleResult, ScreenVerdict
├── rules/                   # Rule ABC + leaf + composite + guards + factory + resolver + methods
├── io/                      # dart_adapter + financial_cache + capital_signals + universe + trail_writer
├── audit/                   # citation + violation + invariants + log
├── application/             # screen orchestrator (+ peer_builder stub)
├── config/                  # profiles + strategies + hard_guards + methods_manifest
└── .guidelines/             # 도메인 로컬 컨벤션
```

`.guidelines/` 의 모든 파일은 편집 / 탐색 시 `inject_guidelines` hook 이 자동 inject — 본 디렉토리에 들어오는 모든 작업이 자동으로 본 컨벤션을 context 에 갖춤.
