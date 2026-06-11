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

`ScanResult` = `catalysts: tuple[CatalystEvent, ...]` / `d_orphans: tuple[...]` / `stats: dict`. orchestrator 는 **I/O 0** — 로딩 / envelope / write 는 `main.py` 책임.

## scan flow

1. **Fan-in (discovery)** — `not dry_run and ctx.universe` 일 때만 각 detector 순회, `enabled` False 인 것 skip
2. **G15 augment / orphan** — `augment_d_type_into_primary(events)`:
   - ticker 별 group. a/b-type 은 primary
   - d_type 은 같은 ticker primary 의 `metadata["d_type_augments"]` 리스트에 attach
   - 같은 ticker primary 없는 d_type → `d_orphans` (candidates 제외, stats 에만 노출)
   - 근거: **D-type 은 단독 trigger 불가**
3. **quality marker** — 각 candidate 에 `metadata["quality_pass_at_stage2"]` 설정
4. **stats + emit** — `(ScanResult(...), detector_warnings)` 반환

## shared adapter 사용

| detector | 외부 스캔 경로 |
|---|---|
| treasury / spin_off_merger / activist (3 DART) | `domains/_shared/adapters/disclosure_scan.scan_disclosures` |
| nav_discount_narrowing | `domains/_shared/nav_history` |
| index_deletion / earnings_panic | catalyst-local `io/{...}_fetch.py` |

## detector 실행 순서 = config 순서 (byte-parity)

`config/detectors.yaml` 의 `detectors:` 리스트 순서 = 실행 순서. 순서 변경은 golden snapshot 회귀를 깬다. 현재 순서: `treasury → spin_off → activist → index → earnings → nav`.
