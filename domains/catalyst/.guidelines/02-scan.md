# Scan — Orchestrator + G15 Augment

## orchestrator (`application/scan_catalysts.py`)

```python
def scan_catalysts(
    *,
    detectors: Sequence[CatalystDetector],
    ctx: DetectContext,
    quality_pass: set[str],
    dry_run: bool,
) -> tuple[ScanResult, list[str]]: ...

def augment_d_type_into_primary(
    events: list[CatalystEvent],
) -> tuple[list[CatalystEvent], list[CatalystEvent]]: ...   # (primaries, d_orphans)
```

`ScanResult` = `catalysts: tuple[CatalystEvent, ...]` / `d_orphans: tuple[...]` / `stats: dict`.
orchestrator 는 **I/O 0** — 로딩 (`io/trail_loader`) / envelope / write 는 `main.py` 책임.

## scan flow

1. **Fan-in (discovery)** — `not dry_run and ctx.universe` 일 때만 각 detector 순회,
   `enabled` False 인 것 skip, `d.detect(ctx)` 호출 → `res.events` / `res.warnings` 누적.
   `dry_run` 은 detector 외부 IO 를 막아 universe / quality 파일 read 만 수행.

2. **G15 augment / orphan** — `augment_d_type_into_primary(events)`:
   - ticker 별 group. a/b-type 은 primary.
   - d_type 은 같은 ticker primary 의 `metadata["d_type_augments"]` 리스트에 attach
     (`{catalyst_id, catalyst_type, source_citation}`).
   - 같은 ticker primary 없는 d_type → `d_orphans` (candidates 제외, stats 에만 노출).
   - 근거: **D-type 은 단독 trigger 불가** (행동주의 진입은 A/C 구조 catalyst 동반 시에만 유효).

3. **quality marker** — 각 candidate 에 `metadata["quality_pass_at_stage2"]` 설정:
   `True` / `False` / `"unknown_stage2_missing"` (quality_pass 비었을 때). non-pass ticker 도
   candidate 로 유지 — 최종 reject 는 Stage 4 책임.

4. **stats + emit** — `by_catalyst_type` count + `stats` dict 구성 후
   `(ScanResult(...), detector_warnings)` 반환. warning 은 **raw** 반환 (secret redaction 은
   caller `main.py` 의 `secret_safe_log` 책임 — warning 순서 보존).

## shared adapter 사용

| detector | 외부 스캔 경로 |
|---|---|
| treasury / spin_off_merger / activist (3 DART) | `domains/_shared/adapters/disclosure_scan.scan_disclosures` + `partial(_boundary.dart_iter_disclosures, api_key)` 를 `DisclosureSourcePort` (`domains/_shared/ports/disclosure.py`, `@runtime_checkable Protocol`) 로 주입 |
| nav_discount_narrowing | `domains/_shared/nav_history` (`load_nav_history` / `detect_narrowing` / `list_parents`) |
| index_deletion / earnings_panic | catalyst-local `io/{...}_fetch.py` (shared scan 미사용) |

`scan_disclosures` 공통 동작: stock_code 6자리 검증 → keyword-group first-match → `keep`
callback → dedup → `MatchedDisclosure` yield. detector 별 책임 (`keep` / `dedup_key` /
catalyst_type 매핑 / G7 citation) 은 byte-parity 위해 detector 에 잔류.

## detector 실행 순서 = config 순서 (byte-parity)

`config/detectors.yaml` 의 `detectors:` 리스트 순서 = 실행 순서.
`augment_d_type_into_primary` 의 ticker grouping 이 insertion order 에 의존하므로,
`catalysts` 출력의 byte-호환을 위해 순서 (`treasury → spin_off → activist → index →
earnings → nav`) 를 고정. 순서 변경은 golden snapshot 회귀를 깬다 (`05-config-contract.md`).

## main.py 통합 (참고)

`main.py` 가 `io/trail_loader` 로 universe / quality_pass 로드 → `DetectContext` 구성 →
`build_detectors(cfg)` → `scan_catalysts(...)` → `base_report_envelope` 에 stats/catalysts/
d_type_orphans/warnings 추가 → `write_output_safely` (G20) → `emit_summary` (D-Q-6).
config build 실패 (`ValueError`) → `rule_name="config_build"` blocking 기록 + exit 2.
