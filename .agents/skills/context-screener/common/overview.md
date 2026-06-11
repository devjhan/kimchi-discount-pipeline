# Screener BC Overview

Stage 2 quality filter + 향후 백테스트 인프라. `domains/screener/` 가 self-contained bounded context.

## 4 Anchor

1. **`RuleFactory.build_strategy` 단일 진입점** — 모든 Rule 트리 생성은 본 클래스 통과. 직접 `AndRule(...)` 생성 시 HardGuardWrapper 자동 wrap 누락 (G13 우회)
2. **`resolver.resolve_metric` 화이트리스트** — 등록된 metric_path 만 허용. `eval()` / `getattr(snapshot, dynamic)` 일체 금지
3. **`clock.can_see` IO 한정** — 시점 가시화는 `LiveFinancialCache` / `PointInTimeFinancialCache` 가 단독 책임
4. **`_boundary.py` 단일 외부 게이트** → Ports & Adapters: `application/`·`domain/` 은 `_boundary` import 0, port Protocol 에만 의존

## 패키지 구조

```
domains/screener/
  main.py / _boundary.py / errors.py / schemas.py
  time/                    # AsOfClock + KRX calendar wrapper
  domain/                  # TickerSnapshot, FilingMetric, RuleResult, ScreenVerdict
  rules/                   # Rule ABC + leaf + composite + guards + factory + resolver + methods
  io/                      # dart_adapter + financial_cache + capital_signals + universe_loader + trail_writer
  audit/                   # citation + violation + invariants + log
  application/             # screen orchestrator (+ peer_builder stub)
  config/                  # profiles + strategies + hard_guards + methods_manifest
  .guidelines/             # 도메인 로컬 컨벤션
```

## 외부 연결점

### Inbound (read)
| # | 외부 객체 | 어댑터 | 변환 |
|---|---|---|---|
| 1 | DART API | `io/dart_adapter.py` (via `_boundary.dart_*`) | `FilingMetric` list + capital_signals events |
| 2 | `$TRAIL_TODAY/01-universe.json` | `io/universe_loader.py` | `UniverseEntry` tuple |
| 3 | KRX holiday data | `time/calendar.py` (via `_boundary.is_trading_day`) | `bool` |
| 4 | System clock | `time/clock.py` | `AsOfClock` |
| 5 | 경로 | `_boundary.resolve_path` / `profiles_root` | `Path` |

### Outbound (write)
| # | 외부 객체 | 어댑터 | 형식 |
|---|---|---|---|
| 1 | `$TRAIL_TODAY/02-quality-filter.json` | `io/trail_writer.py` | D-Q-2 envelope + verdicts |
| 2 | `$TRAIL_TODAY/02-fin-fetch.json` (선택) | `io/trail_writer.py` | D-Q-2 envelope |
| 3 | stdout handoff 1줄 | `_boundary.emit_summary` | D-Q-6 `[stage2-screener] ...` |
| 4 | violation log | `audit/log.py` | JSONL append-only |
| 5 | live cache | `io/financial_cache.LiveFinancialCache` | v4 schema |

### Downstream consumer
| Consumer | 위치 | Read | 보장 |
|---|---|---|---|
| Stage 3 catalyst scan | `domains/catalyst/main.py` | `verdicts[].verdict == "pass"` | path / schema name 보존 |
| Stage 4 thesis-auditor | skill | 산출 존재 + verdict | envelope 보존 |
| Stage 6 brief-author | skill | `verdicts[]` 인용 | citation G7 보존 |
| Quality lens | skill `stage2-quality-lens` | `verdict == "pass"` 만 | verdict 필드 보존 |
| Audit shadow | `domains.audit_integrity.main` | `verdicts[]` (tier_3 pool) | append-only |

## Ports & Adapters (feature-first hexagonal)

`_boundary.py` 는 fat god-facade 에서 **typed adapter factory** 로 진화 중. 외부 의존을 narrow `typing.Protocol` **port** 로 선언, `_boundary` 가 concrete **adapter** 구성, composition root (`main.py`) 가 순수 use-case 에 주입.

| 요소 | 위치 | 비고 |
|---|---|---|
| **Port (Protocol)** — cross-cutting | `domains/_shared/ports/*.py` | ≥2 BC 공유 (CitationPort / ClockPort) |
| **Port (Protocol)** — BC-local | `domains/<bc>/ports/*.py` | 1 BC 전용 |
| **Adapter (impl)** | `_boundary.py` (유일 infra-import 파일) | factory 함수 `xxx_adapter() -> XxxPort` |
| **Composition root** | `main.py` | 어댑터를 use-case 에 주입 |

**불변식**: `application/` · `domain/` 은 `_boundary` import 0 (port Protocol 에만 의존). 게이트 *삭제* 금지 — D-CORE-4 강제.
