# financial_cache — Live vs PointInTime

## 두 구현의 책임 분리

| 구현 | use case | layout | schema |
|---|---|---|---|
| `LiveFinancialCache` | 일별 cron 의 latest cache | 단일 파일 (`{ticker_safe}.json`) | `investment-stage2-fin-cache-v4` |
| `PointInTimeFinancialCache` | 백테스트 결정론 | 다중 파일 (`{ticker}/{period}/{filing_dt}.json`) | (Phase 2 정의) |

PR2 단계는 Live 본 구현 + PIT stub. 백테스트 도입 시 PIT 추가.

## clock.can_see boundary

**핵심**: `clock.can_see(filing_datetime)` 호출은 **IO layer (cache)** 에서만. Rule / domain / application 모듈은 clock 을 받기만 함.

```python
# ✅ 올바름 — cache 가 시점 가시화 단독 책임
class PointInTimeFinancialCache(FinancialCacheBase):
    def get_snapshot(self, ticker, name, clock):
        visible_filings = [f for f in all_filings if clock.can_see(f.filing_datetime)]
        ...

# ❌ 금지 — Rule 이 시점 의식
class MyRule(Rule):
    def evaluate(self, snapshot):
        if not snapshot.clock.can_see(some_event):  # 절대 금지
            ...
```

본 분리가 깨지면 백테스트 시 어떤 데이터가 어느 시점에 보였는지 추적 불가.

## v4 schema 구조

```json
{
  "schema": "investment-stage2-fin-cache-v4",
  "ticker": "KR:005930",
  "name": "...",
  "corp_code": "...",
  "fetched_at": "ISO_KST",
  "bsns_year": "2024",
  "tax_rate": 0.22,
  "_cache_meta": {
    "financials": {"fetched_at_epoch": ..., "ttl_seconds": ...},
    "capital_signals": {"fetched_at_epoch": ..., "ttl_seconds": ...}
  },
  "filings": [
    {"fiscal_period": "2024Y", "period_end_date": "2024-12-31",
     "filing_datetime": "ISO_KST", "kind": "annual", ...}
  ],
  "capital_signals_events": [
    {"event_datetime": "ISO_KST", "signal_type": "dividend_payment", "citation": "..."}
  ],
  "metrics": {...},
  "citations": [...]
}
```

v3 (legacy) 는 raw filings 부재 — schema mismatch 로 cache miss. 다음 fetch 가 v4 로 overwrite.

## TTL / grace

`config/strategies/{name}.yaml.constants.financial_cache`:
- `financials_ttl_days: 30`
- `capital_signals_ttl_days: 7`
- `staleness_grace_days: 14`

`LiveFinancialCache.is_fresh(ticker, layer, now_epoch)` → TTL 신선도. `is_within_grace` → DART fail 시 G8 graceful fallback 진입 게이트 (실제 fetch 흐름에 통합은 후속 PR).

## atomic write

cache 디렉토리는 매일 같은 path 갱신 의도이므로 `write_output_safely` 의 `.{N}.json` suffix 패턴 부적합. `tmp.replace(path)` atomic write — `infrastructure/dart/client.py` 의 corp_code atomic write 직역.
