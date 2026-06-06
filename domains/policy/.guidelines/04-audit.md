# Audit — drift violation + commit-gate enforcement

## ViolationLog (`audit/log.py`)

`domains.policy.audit.log.ViolationLog` 는 `domains._shared.audit.log.ViolationLog` 의 thin
subclass (`bc_name="policy"`, `audit_dir=lambda: _boundary.resolve_path("operations_audit")`).
shared base: `record(violation) -> Path`, `has_blocking` property.
`GuardViolation` 은 `audit/violation.py` (= `_shared` re-export).

### 유일한 rule_name = `"profile_drift"`

`application/commit.py` 가 `ruling.exceeds_threshold` 시 1건 기록:
- `rule_name="profile_drift"`, `message=f"Δ{max_threshold_delta:.2f} > {drift_threshold}"`
- `context` = `max_threshold_delta` / `drift_threshold` / `changed_thresholds`
- `ticker=out.ticker`, `detected_at=_boundary.now_kst()`
- **severity** = `"blocking" if ruling.blocks_commit else "warning"` — 현재 항상 `"warning"`
  (`DRIFT_BLOCKS_COMMIT=False`)

JSONL: `$AUDIT_DIR/policy-violations/{date}.jsonl` (append-only, date-partition).
citation helper 도 re-export (`CITATION_RE` / `is_valid_citation` / `filter_valid_citations`).

## 강제 모델 (JSONL 외)

본 BC 는 runtime invariant 보다 **결정론 commit-gate** 로 정합성 강제:
1. `EnrichCutoffProfile.__post_init__` shape 검증 (`ProfileSchemaError`)
2. `shape_validate_cutoff_rules` (`"type"` 키 없으면 `ValueError`)
3. versioned write never overwrite (G20, `write_profile_safely` + `v{N}.yaml`)
4. drift audit + 선택적 hard-block (`ProfileDriftError`)

## 적용 G-guard

| G | 내용 | policy 적용 |
|---|---|---|
| G6 | 정량 계산 Python 단독, LLM 계산 금지 | drift/version/provenance 산술은 pure `commit_gate.py`+`drift.py`; PolicyEngine 은 qualitative draft 만 |
| **ADR-0003** | LLM drafts, Python commits | phase2 skill 은 `_profile-draft-*.json` 만; phase3 `_commit_from_draft → commit_profile → decide_commit` 이 version/drift/provenance/write 결정론. **스킬은 commit 권한 없음** |
| G7 | 숫자는 `{source}@{ISO}={value}` citation | `Provenance.citations` / `ResearchOutput.citations` 가 G7 채널 (`DART@<iso>=<value>`) |
| G10 | 외부 신호는 `/ingest-external-signal` 만 | `Trigger` 는 `payload_ref` 만; evidence 는 `config/signals/{ticker_dir}/` (ingest SOP 산출) |
| G20 | overwrite 금지, date/version 보존 | `write_profile_safely`/`write_output_safely` collision-safe; 새 version 은 새 `v{N}.yaml`; audit JSONL date-partition |

ADR-0003 의 구조적 enforcement = "스킬은 commit 안 함" — phase2/phase3 분리가 곧 G6 의 정책 적용.
