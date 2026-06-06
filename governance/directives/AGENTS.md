# Coding Directives — 인덱스

본 디렉토리 (`$DIRECTIVES_DIR`) 는 investment_v3 의 **"어떻게 작성하는가"** 규약 모음이다.
`$AXIOMS_DIR` (왜) 와 `$SPECS_DIR/hard-guards.md` (도메인 무엇) 의 자매 계층 — **언어·포맷·운영 관점의 코딩 룰**.

각 directive 는 `D-{LANG}-{N}` 형식의 고유 ID 를 가지며, hook (`block_anti_patterns.sh` / `lint_directives.sh` / `inject_directive_context.sh`) 이 이 ID 를 stderr 인용해 사용자·에이전트에게 위반 사실 + 실행가능한 대안을 동시에 전달한다.

---

## D-ID ↔ 파일 매핑

| ID 범위 | 파일 | 주제 |
|---|---|---|
| D-CORE-* | [00-principles.md](00-principles.md) | 대원칙 (KISS / YAGNI / DRY / 모듈 경계 / 의존성 정책) |
| D-ARCH-* | [05-architecture.md](05-architecture.md) | 아키텍처/배치 판단 기준 (중앙-분산 / 통폐합 CCP·CRP·ISP / 의존방향 / 포트 수명주기 / 문서표준 / ADR 기록) |
| D-PY-* | [10-python.md](10-python.md) | Python 작성 컨벤션 (typing, dataclass, docstring, import, error pattern) |
| D-SH-* | [11-shell.md](11-shell.md) | Shell hook 작성 (shebang, `set -uo pipefail`, stderr 1-3 줄, exit code) |
| D-CFG-* | [12-config-text.md](12-config-text.md) | YAML / JSON / `.env` / Markdown 작성 표준 (envelope, schema, citation) |
| D-Q-* | [20-quality.md](20-quality.md) | 에러 핸들링 / 테스트 / 로깅 / 관측성 |
| D-SEC-* | [30-security.md](30-security.md) | secret redact / 하드코딩 금지 / alias-only path / 자동매매·주문 차단 |

---

## Hook ↔ Directive 매핑

| Hook | 단계 | 적용 D-ID | 모드 |
|---|---|---|---|
| `inject_directive_context.sh` | UserPromptSubmit | 매칭된 언어별 directive 전체 | inject only |
| `block_anti_patterns.sh` | PreToolUse (Write/Edit) | D-PY-1, D-SH-1, D-CFG-1, D-SEC-1 | fail-closed (exit 2) |
| `lint_directives.sh` | PostToolUse (Write/Edit) | D-PY-2~5, D-SH-2~4, D-CFG-2~3, D-Q-*, D-SEC-2~3 | dry-run (M1) → enforce (M2) |
| (none) | — | **D-ARCH-\*** | inject-only / fitness test |

> **D-ARCH 는 write-time hook 이 없다 — 위 "각 D-ID 가 hook 으로 강제된다" 가정의 예외.**
> 구조 불변식은 per-file syntactic 검사가 아니라 repo-wide AST 검사라야 의미가 있어
> **fitness test** (`tests/architecture/`, `make test-arch`)로 강제하고(D-ARCH-3/4/5/6),
> 나머지는 inject-only 다. `_directive_lint.py` 의 D-ID 정규식(`D-[A-Z]+-\d+`)·`*.md` glob 은
> D-ARCH 를 자동 인식하므로 hook 코드 변경은 불필요.

---

## Directive 본문 컨벤션 (각 파일 공통)

각 D-ID 절은 다음 4 요소를 모두 포함한다:

1. **제목**: `## D-XX-N — 한 줄 룰 요약`
2. **근거**: 왜 이 룰이 존재하는가 (1-2 줄)
3. **❌ / ✅ 코드 예시**: 가장 짧은 위반 / 올바른 작성
4. **Hook**: 어느 hook 이 어떻게 검사하는지 (`inject_only` 인 경우 명시)

---

## 우선순위 (다중 룰 충돌 시)

```
$AXIOMS_DIR (5 axiom)
   ↓ (이념적 충돌 시 우선)
$SPECS_DIR/hard-guards.md (G-rule)
   ↓ (도메인 룰 충돌 시 우선)
$DIRECTIVES_DIR (본 인덱스 + 자매 파일)
```

D-ID 가 G-rule 과 충돌하면 G-rule 이 이긴다. 충돌은 PR/리뷰 시 인용한다 (자동 cross-check linter 는 제거됨).

---

## 새 D-ID 추가 절차

1. 본 AGENTS.md 의 "D-ID ↔ 파일 매핑" 표에 해당 파일을 확인 (없으면 새 파일 추가)
2. 해당 파일 본문에 `## D-XX-N — 룰 제목` 절 추가 (4 요소 포함)
3. hook 으로 강제할 경우 `$HOOKS_DIR/_directive_lint.py` 에 검사 함수 추가
4. UserPromptSubmit 시 `inject_directive_context` 가 본문을 주입하는지, `block_anti_patterns` / `lint_directives` 가 새 D-ID 를 인식하는지 확인
