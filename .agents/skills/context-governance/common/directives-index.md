# Directives — 코딩 컨벤션 (D-ID)

> **원본**: `governance/directives/00-principles.md` ~ `30-security.md` (6파일)
> **본 파일**: agent-readable 인덱스. 충돌 시 원본 우선. 상세 근거·코드 예시는 원본 참조.

## D-ID ↔ 파일 매핑

| ID 범위 | 파일 | 주제 |
|---|---|---|
| D-CORE-* | `governance/directives/00-principles.md` | 대원칙 (KISS / YAGNI / DRY / 모듈 경계 / 의존성 정책) |
| D-ARCH-* | `governance/directives/05-architecture.md` | 아키텍처/배치 판단 기준 (중앙-분산 / 통폐합 CCP·CRP·ISP / 의존방향 / 포트 수명주기 / 문서표준 / ADR 기록) |
| D-PY-* | `governance/directives/10-python.md` | Python 작성 컨벤션 (typing, dataclass, docstring, import, error pattern) |
| D-CFG-* | `governance/directives/12-config-text.md` | YAML / JSON / `.env` / Markdown 작성 표준 (envelope, schema, citation) |
| D-Q-* | `governance/directives/20-quality.md` | 에러 핸들링 / 테스트 / 로깅 / 관측성 |
| D-SEC-* | `governance/directives/30-security.md` | secret redact / 하드코딩 금지 / alias-only path / 자동매매·주문 차단 |

## D-ID 1줄 요약

| ID | 1줄 |
|---|---|
| D-CORE-1 | SSoT — path/임계값 중복 선언 금지, `utils.py` path helper 사용 |
| D-CORE-2 | KISS — 3줄 반복을 추상화로 포장하지 않음 |
| D-CORE-3 | Default No-Action — 빈 산출물이 정상, fallback 자동 채움 금지 |
| D-CORE-4 | 4-layer 단방향 의존 (governance ← infra ← domains → operations) |
| D-CORE-5 | 새 third-party 의존 최소화, `pyproject.toml` 에 version cap |
| D-CORE-6 | 작업 전 Read, 변경 후 verify (pytest / import 확인) |
| D-CORE-7 | LLM 호출은 단일 port (`infrastructure/llm` dispatcher), vendor 종속은 bounded adapter |
| D-ARCH-1 | 중앙/분산 배치 = 소유·변경빈도·독자범위 축 (파일포맷 오인 금지) |
| D-ARCH-2 | 통폐합 = CCP·CRP·SDP 기준 — 함께 변하면 함께, 변경축 다르면 분리 |
| D-ARCH-3 | 의존 방향 단방향 불변식 (fitness test `test_dependency_direction.py`) |
| D-ARCH-4 | `_boundary` 는 typed adapter factory — 좁은 Protocol port 로 god-module 방지 |
| D-ARCH-5 | 모든 BC = `AGENTS.md` + `.guidelines/` 6파일 (문서 표준, `test_doc_completeness.py`) |
| D-ARCH-6 | 구조 결정은 ADR 로 — 기각도 `Rejected-proposal` 로 영구, 반복 패턴은 D-ARCH 승격 |
| D-PY-1 | 모든 `.py` 헤더에 `from __future__ import annotations` |
| D-PY-2 | public 함수 서명에 타입 힌트 의무 |
| D-PY-3 | `except Exception` 은 `# noqa: BLE001` 코멘트 또는 명시적 타입 catch |
| D-PY-4 | import 순서: future → stdlib → third-party → local (그룹 간 빈 줄) |
| D-PY-5 | 함수/모듈 docstring 1~3줄 한국어 의무 (public 함수 한정) |
| D-PY-6 | fatal → `SystemExit`, recoverable → `(data, err)` tuple |
| D-PY-7 | 새 모듈은 `if __name__ == "__main__":` 진입점 보장 |
| D-CFG-1 | governance YAML 헤더에 `version:` + `description:` 강제 |
| D-CFG-2 | JSON 산출물 envelope 5필드 (`schema`, `generated_at`, `date`, `config_version`, `warnings`) |
| D-CFG-3 | YAML 들여쓰기 2칸, 탭 금지 |
| D-CFG-4 | Markdown 숫자는 `SRC@ISO_TS=VALUE` citation 의무 |
| D-CFG-5 | `.env` / secret 내용 본문 직접 인용 절대 금지 (`secret_safe_log` 사용) |
| D-CFG-6 | Markdown forbidden language — "should buy", "guaranteed", "alpha confirmed" 등 금지 |
| D-Q-1 | 외부 I/O 는 항상 `timeout=` + retry budget 명시 |
| D-Q-2 | 빈 산출물도 envelope 5필드 채워 write (`write_output_safely` G20 보존) |
| D-Q-3 | 모든 도메인 helper 는 pytest 가능 (`tests/unit/test_{module}.py` 1개 이상) |
| D-Q-4 | 로깅: `print(stdout)` handoff / `print(stderr)` 경고 — `logging` 모듈 금지 |
| D-Q-5 | `telemetry/` retention class(PERMANENT/STATE/SNAPSHOT/BINARY/EPHEMERAL) 분리 + registry SSoT — `/context-telemetry` |
| D-Q-6 | `emit_summary_line` 표준 — `[stageN] verdict=... key=value -> path` |
| D-SEC-1 | secret-like literal 본문 매립 금지 (regex prefix-bound guard) |
| D-SEC-2 | `$ENV_PATH` 직접 Read/Bash/Write/Edit 차단 (`pre_env_guard.sh`) |
| D-SEC-3 | 자동매매·주문 호출 절대 금지 — KIS read-only whitelist 만 허용 (G9) |
| D-SEC-4 | Alias-only path — 절대경로 금지, `os.environ["ALIAS"]` 경유 |
| D-SEC-5 | 외부 신호 ingest 는 `/ingest-external-signal` 명령으로만 (G10) |
| D-SEC-6 | `_hook_audit.log` 본문에 secret 값 echo 금지 — 변수 이름만 인용 |
