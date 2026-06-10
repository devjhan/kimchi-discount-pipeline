# Coding Directives — 인덱스

본 디렉토리 (`$DIRECTIVES_DIR`) 는 investment_v3 의 **"어떻게 작성하는가"** 규약 모음이다.
$AXIOMS_DIR (왜) 의 자매 계층 — **언어·포맷·운영 관점의 코딩 룰**.

각 directive 는 `D-{LANG}-{N}` 형식의 고유 ID 를 가진다.

---

## D-ID ↔ 파일 매핑

| ID 범위 | 파일 | 주제 |
|---|---|---|
| D-CORE-* | [00-principles.md](00-principles.md) | 대원칙 (KISS / YAGNI / DRY / 모듈 경계 / 의존성 정책) |
| D-ARCH-* | [05-architecture.md](05-architecture.md) | 아키텍처/배치 판단 기준 (중앙-분산 / 통폐합 CCP·CRP·ISP / 의존방향 / 포트 수명주기 / 문서표준 / ADR 기록) |
| D-PY-* | [10-python.md](10-python.md) | Python 작성 컨벤션 (typing, dataclass, docstring, import, error pattern) |
| D-SH-* | ~~[11-shell.md](11-shell.md)~~ | Shell 컨벤션 — AGENTS.md 와 run_daily_local.sh 참조 (독립 문서 삭제됨) |
| D-CFG-* | [12-config-text.md](12-config-text.md) | YAML / JSON / `.env` / Markdown 작성 표준 (envelope, schema, citation) |
| D-Q-* | [20-quality.md](20-quality.md) | 에러 핸들링 / 테스트 / 로깅 / 관측성 |
| D-SEC-* | [30-security.md](30-security.md) | secret redact / 하드코딩 금지 / alias-only path / 자동매매·주문 차단 |

---

## Hook ↔ Directive 매핑

Claude Code hook 시스템은 파기되었다 (ADR-0027). directive 는 현재 pre-commit lint +
code review 시 참조 reference 로만 사용된다. D-ARCH 불변식은
**fitness test** (`tests/architecture/`, `make test-arch`)로 강제한다.

---

## Directive 본문 컨벤션 (각 파일 공통)

각 D-ID 절은 다음 4 요소를 모두 포함한다:

1. **제목**: `## D-XX-N — 한 줄 룰 요약`
2. **근거**: 왜 이 룰이 존재하는가 (1-2 줄)
3. **❌ / ✅ 코드 예시**: 가장 짧은 위반 / 올바른 작성
4. **적용**: 이 룰이 어떻게 적용되는지 (pre-commit / review / fitness test)

---

## 우선순위 (다중 룰 충돌 시)

```
$AXIOMS_DIR (5 axiom)
   ↓ (이념적 충돌 시 우선)
AGENTS.md G1-G22 (Hard Guards)
   ↓ (도메인 룰 충돌 시 우선)
$DIRECTIVES_DIR (본 인덱스 + 자매 파일)
```

D-ID 가 G-rule 과 충돌하면 G-rule 이 이긴다. 충돌은 PR/리뷰 시 인용한다.

---

## 새 D-ID 추가 절차

1. 본 AGENTS.md 의 "D-ID ↔ 파일 매핑" 표에 해당 파일을 확인 (없으면 새 파일 추가)
2. 해당 파일 본문에 `## D-XX-N — 룰 제목` 절 추가 (4 요소 포함)
3. pre-commit hook 또는 code review 시 참조 reference 로 인용
