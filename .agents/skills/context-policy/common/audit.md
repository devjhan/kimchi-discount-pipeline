# Audit — drift violation + commit-gate enforcement

## ViolationLog (`audit/log.py`)

`ViolationLog` 는 `_shared.audit.log.ViolationLog` 의 thin subclass (`bc_name="policy"`). JSONL: `$AUDIT_DIR/policy-violations/{date}.jsonl`.

### 유일한 rule_name = `"profile_drift"`

`application/commit.py` 가 `ruling.exceeds_threshold` 시 1건 기록:
- `rule_name="profile_drift"`, `message=f"Δ{max_threshold_delta:.2f} > {drift_threshold}"`
- **severity** = `"blocking" if ruling.blocks_commit else "warning"` — 현재 항상 `"warning"` (`DRIFT_BLOCKS_COMMIT=False`)

## 적용 G-guard

| G | 내용 | policy 적용 |
|---|---|---|
| G6 | 정량 계산 Python 단독 | drift/version/provenance 산술은 pure `commit_gate.py`+`drift.py` |
| **ADR-0003** | LLM drafts, Python commits | phase2 skill 은 `_profile-draft-*.json` 만; phase3 결정론 commit |
| G7 | 숫자는 `{source}@{ISO}={value}` citation | `Provenance.citations` / `ResearchOutput.citations` |
| G10 | 외부 신호는 `/ingest-external-signal` 만 | `Trigger` 는 `payload_ref` 만; evidence 는 `config/signals/` |
| G20 | overwrite 금지 | `write_profile_safely`/`write_output_safely` collision-safe |

## 강제 모델 (JSONL 외)

1. `EnrichCutoffProfile.__post_init__` shape 검증 (`ProfileSchemaError`)
2. `shape_validate_cutoff_rules` (`"type"` 키 없으면 `ValueError`)
3. versioned write never overwrite (G20)
4. drift audit + 선택적 hard-block (`ProfileDriftError`)
