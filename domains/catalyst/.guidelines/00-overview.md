# catalyst — DDD Modular Monolith Overview

투자 파이프라인 Stage 3 의 catalyst event scan. Stage 2 quality-pass 종목에 대해
**catalyst trigger** (A-type 자사주소각/분할/NAV좁힘 · B-type forced-selling/panic ·
D-type 행동주의) 를 6 `CatalystDetector` plugin 으로 fan-in 탐지하고, G15 d_type augment
규칙을 적용한 뒤 단일 Stage 3 envelope 를 emit 한다. 구 `alpha_factory.catalyst_scan`
(3 CLI step → 1) 의 후신이며 `domains/universe` · `domains/screener` 와 isomorphic 한 BC.

## 4 Anchor (변경 시 도메인 안정성 영향)

1. **`detectors/factory.build_detector` 단일 진입점** — 모든 `CatalystDetector` 인스턴스화는
   본 함수 통과. 직접 concrete-class 생성 시 registry 외 detector type 우회 통로가 열린다.
   `build_detectors` 는 `enabled: false` 도 build 하고 (flag 보존) skip 은 orchestrator 책임.

2. **`detectors/registry.register_detector` decorator + `DETECTOR_TYPES` dict** — 모든 detector
   클래스는 본 decorator 부착되어야 factory dispatch 가능. 중복 등록은 `ValueError`
   (silent override 금지). 신규 detector 파일은 `factory.py` 에 import 1줄 추가 필수
   (`@register_detector` 부작용 트리거).

3. **`_boundary.py` 단일 외부 게이트** — 다른 catalyst 모듈이 `infrastructure.*` /
   `os.environ` / path 직접 해석 시 컨벤션 위반. 검증:
   `grep -rn "from infrastructure" domains/catalyst/ --include="*.py" | grep -v _boundary.py`
   결과는 0 줄 (`03-boundaries.md` 참조).

4. **공유 clock SSoT (`domains._shared.time.clock.AsOfClock`)** — catalyst 는 자체 clock 정의
   금지. `main.py` 가 `AsOfClock.at_market_close(...)` 로 생성해 `DetectContext` 로 전파.
   (보조 anchor: 3 DART detector 는 `domains._shared.adapters.disclosure_scan.scan_disclosures`
   공유 스켈레톤 사용 — F-16, `_boundary.dart_iter_disclosures` 를 `DisclosureSourcePort` 로 주입.)

## 패키지 핵심 객체

### domain/ — frozen value object
- `event.py` `CatalystEvent` — `catalyst_id` / `ticker` / `name` / `catalyst_type` /
  `trigger_class` (`a_type`|`b_type`|`d_type`) / `detected_at` / `source_citation` /
  `metadata`. `frozen=True` 지만 `metadata` dict 내용은 orchestrator (d_type augment +
  quality marker) 가 의도적으로 변경 — 모듈 docstring 명시.

### detectors/ — CatalystDetector plugin (6)
- `base.py` `CatalystDetector` ABC (`name` / `enabled`) + `DetectContext` + `DetectResult`
- `registry.py` `DETECTOR_TYPES` + `@register_detector(name)` (dup → ValueError)
- `factory.py` `build_detector(spec)` + `build_detectors(specs)` — detectors.yaml dispatch
- 6 concrete: `treasury_cancellation` / `spin_off_merger` / `activist_5pct` /
  `index_deletion` / `earnings_panic` / `nav_discount_narrowing` (`01-detectors.md` 카탈로그)

### application/ — orchestrator (I/O 0)
- `scan_catalysts.py` `scan_catalysts(...)` + `augment_d_type_into_primary(...)` + `ScanResult`
  (`catalysts` / `d_orphans` / `stats`). 로딩 / envelope / write 는 `main.py` 책임.

### io/ — typed loaders + 일부 vendor fetch
- `trail_loader.py` — `load_universe_tickers` / `load_universe_market` / `load_quality_pass`
  (Stage 1/2 산출물 read)
- `index_deletion_fetch.py` — `discover_index_deletions` + `IndexDeletionEntry`
- `earnings_panic_fetch.py` — `discover_earnings_announcements` / `evaluate_announcement` 등
  (NAV history 는 `domains/_shared/nav_history.py` 사용 — 구 `io/nav_history_cache` 는 소멸)

### audit/ — invariant + JSONL log (thin shim over `_shared/audit`)
- `invariants.py` `validate_g7_citations` + `CitationViolation` (현재 main.py 미연결 — `04-audit.md`)
- `log.py` `ViolationLog` (bc_name="catalyst") / `violation.py` / `citation.py` — `_shared` 재노출

### config/ — self-contained YAML
- `detectors.yaml` — 활성 detector 목록 + per-detector spec (schema `catalyst-detectors-v1`)

### main.py — CLI entry
- `--date` / `--dry-run` / `--trail-dir` / `--allow-yahoo-fallback`
- exit 0 / 2 (config build 실패 또는 `violation_log.has_blocking` 시 2)

## 산출 / 외부 연결점

- 산출: `$TRAIL_TODAY/03-catalyst-events.json` (envelope schema `investment-stage3-catalyst-events-v1`,
  `write_output_safely` G20)
- audit log: `$AUDIT_DIR/catalyst-violations/{date}.jsonl` (현재 healthy run 은 미생성 — `04-audit.md`)
- handoff: stdout 1줄 (`emit_summary("stage3-catalyst-scan", ...)`) → 출력 경로
- 입력: `01-universe.json` + `02-quality-filter.json` (Stage 1/2 산출물, `io/trail_loader`)
- 외부 의존 (ACL 통과): DART (disclosures) / KIS (일봉) / Yahoo (fallback) / `_shared` nav_history·disclosure_scan
- 외부 도메인 호출: 없음 — catalyst 는 Stage 1/2 *consumer*, 산출물은 Stage 4 (brief gate) 가 read

## envelope 구조

`03-catalyst-events.json` 은 `base_report_envelope` (D-Q-2) 에 다음을 추가:

```jsonc
{
  "schema": "investment-stage3-catalyst-events-v1",
  "generated_at": "ISO 8601 KST",
  "date": "YYYY-MM-DD",
  "config_path": "absolute path to detectors.yaml",
  "config_version": int,
  "stats": {                          // ScanResult.stats
    "total_candidates": int,
    "by_catalyst_type": {type: count},
    "d_type_orphans_excluded": int,
    "universe_size": int,
    "quality_pass_size": int,
    "dry_run": bool
  },
  "catalysts": [ /* asdict(CatalystEvent) */ ],
  "d_type_orphans": [ /* G15 orphan d_type, candidates 제외 */ ],
  "warnings": [...]                   // secret_safe_log 통과 (main.py)
}
```
