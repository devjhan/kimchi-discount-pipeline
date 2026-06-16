# D-Q — Quality: 에러 핸들링 / 테스트 / 로깅 / 관측성

코드 품질을 떠받치는 cross-language 룰. Python 특화는 D-PY-3/D-PY-6 참조.

---

## D-Q-1 — 외부 I/O 는 항상 timeout + retry budget 명시

**근거**: DART / KIS / Yahoo / FRED 가 hang 하면 cron 전체가 멈춤. 모든 HTTP / file lock / DB 호출은 timeout 의무 + retry 횟수 의식적 결정.

❌ 금지
```python
r = requests.get(url)            # timeout 없음
data = open(path).read()         # 절대 path / lock 미지정
```

✅ 올바름
```python
r = requests.get(url, timeout=(5, 30))   # connect=5s, read=30s
r.raise_for_status()
```

infrastructure clients 가 `_with_retry()` wrapper 를 사용 — 새 client 도 동일 패턴 따를 것.

**Hook**: `lint_directives.sh` (PostToolUse, M2) — `requests.(get|post|put)\(` 의 `timeout=` kwarg 부재 시 violation.

---

## D-Q-2 — 빈 산출물도 envelope 형태로 write

**근거**: D-CORE-3 (no-action default) 의 implementation 측면. items=[] 인 stage 산출물이라도 envelope 5 필드는 항상 채워 cross-stage read 가 KeyError 안 나도록.

✅ 올바름
```python
write_output_safely(
    trail_today / "03-catalyst-events.json",
    {
        "schema": "stage3-catalyst-v1",
        "generated_at": now_iso(),
        "date": today,
        "config_version": "thresholds-1.4",
        "warnings": [],
        "items": [],         # 빈 list OK
    },
)
```

`$INFRA_COMMON_DIR/utils.py` 의 `write_output_safely()` 는 동일 path 충돌 시 자동 `.{N}.json` suffix 보존.

**Hook**: `lint_directives.sh` (PostToolUse) — items 만 있고 envelope 부재 시 violation.

---

## D-Q-3 — 모든 도메인 helper 는 pytest 가능 (`tests/` 디렉토리)

**근거**: 본 시스템은 cron 일별 실행 + 한국 시장 휴장일 / 비영업일 / DART rate-limit 등 환경 의존. unit test 가 없으면 regression 추적 불가. 새 helper 추가 시 같이 `tests/unit/test_{module}.py` 1 개 이상.

✅ 표준 fixture
```python
# tests/conftest.py 의 isolated_workspace 사용
def test_compute_kelly_cap(isolated_workspace):
    result = compute_kelly_cap(equity_curve=[1.0, 0.95, 1.02])
    assert result <= 0.5  # G2-A 의 fractional Kelly cap
```

monkeypatch 로 alias env 주입 (실제 cron 환경 흉내).

**Hook**: `inject_only` — PR 시 인용. 새 도메인 helper 추가 시 동명 test 파일 부재면 권장.

---

## D-Q-4 — 로깅: `print(stdout)` / `print(stderr)` 표준

**근거**: 본 시스템은 cron 출력을 `$AUDIT_DIR/cron-logs/run-{date}.log` 로 redirect. stdout 은 handoff (`[STAGE_NAME] key=value -> /path`), stderr 는 경고 / 에러. logger 사용 안 함 (이중 출력 회피).

✅ stdout handoff 패턴
```python
print(f"[stage3] verdict=pass items={len(items)} -> {out_path}")
```

✅ stderr 경고 패턴
```python
print(f"[WARN] DART rate-limit hit, retrying in 30s", file=sys.stderr)
```

❌ 금지
```python
logger.info("...")   # logging 모듈 사용 — 본 시스템 표준 아님
```

`secret_safe_log()` 는 stderr / log 가는 모든 메시지에 자동 redact 적용.

**Hook**: `lint_directives.sh` (PostToolUse, M2) — `import logging` 발견 시 warning.

---

## D-Q-5 — 관측성: `telemetry/` retention class 분리 + registry SSoT

**근거**: telemetry 산출물은 lifecycle(수명·재생성 가능성)이 서로 다르다 — append-only 증거 /
living state / point-in-time 스냅샷 / 실행 로그를 한 곳에 섞으면 retention 정책이 충돌한다.
ADR-0008 을 5 보존 클래스(PERMANENT/STATE/SNAPSHOT/BINARY/EPHEMERAL)로 세분하고, 산출물 종류는
`infrastructure/_common/telemetry_registry.py` `REGISTRY` 에 선언한다 (SSoT). 상세는
`/context-telemetry` 스킬.

✅ 표준 layout (concern/생산자 별 subdir; 경로는 `$AUDIT_DIR` = `telemetry/audit`)
```
audit/shadow-portfolio/state.json          # 4-tier paper trade state          [STATE]
audit/shadow-portfolio/trade-log-{tier}.csv # tier별 진입/청산 (append)          [PERMANENT]
audit/scheduler-state/scheduler-state-{date}.json  # launchd/cron drift          [SNAPSHOT]
audit/violations/{bc}/{date}.jsonl         # BC별 룰 위반 (append)              [PERMANENT]
audit/breadth/macro-breadth-{date}.json    # SPX breadth 스냅샷                  [PERMANENT]
audit/subsidiaries/subsidiaries-audit-{date}.json  # 자회사 audit               [PERMANENT]
audit/process-{YYYY-WW}.md                 # 주간 process audit (skill 산출)
audit/outcome-{YYYY-Q}.md                  # 분기 outcome audit (skill 산출)
```
> 실행 로그(`cron/run-{date}.log`)는 `telemetry/logs/` (EPHEMERAL, gitignore) — `$AUDIT_DIR` 아님.
> 구 hook telemetry(`_hook_audit.log`)는 ADR-0010 으로 hook 파기와 함께 제거됨.

**재발 방지**: 신 산출물 종류는 `REGISTRY` 등록 강제 — 미등록 파일은 retention GC 가 ORPHAN 으로
보고, arch 테스트 `test_live_telemetry_has_no_orphans` 가 드리프트를 red 로 만든다.
정리: `make telemetry-gc` (dry-run) / `make telemetry-gc-apply`.

---

## D-Q-6 — emit_summary_line 표준 (stage 간 handoff)

**근거**: cron orchestrator 가 stage 별 verdict 를 parse — `[stage{N}] verdict={pass|fail|no_action} key=value -> path` 한 줄 형식 강제. 자유 텍스트 로그는 grep 불가.

✅ 올바름
```python
from infrastructure._common.utils import emit_summary_line
emit_summary_line(
    "stage2",
    verdict="pass",
    items=12,
    out_path=out_path,
)
```

stdout 출력: `[stage2] verdict=pass items=12 -> $TRAIL_TODAY/02-quality-filter.json`.

**Hook**: `inject_only` — 새 stage helper 추가 시 본 directive 인용.
