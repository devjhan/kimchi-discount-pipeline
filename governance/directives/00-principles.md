# D-CORE — 대원칙

언어·포맷에 무관하게 모든 산출물(코드 / config / hook / 문서)에 적용되는 최상위 코딩 원칙.

---

## D-CORE-1 — Single Source of Truth (alias / 정량 임계값 / G-rule)

**근거**: path / 임계값 / 룰 ID 의 중복 선언은 drift 의 원인. `$TOPOLOGY_PATH`, `$THRESHOLDS_PATH`, `$SPECS_DIR/hard-guards.md` 가 각각 단일 source. 본문에 raw 값을 박지 말고 SSoT 참조.

❌ 금지
```python
KIS_BASE = "/Users/me/projects/investment_v3/.env"   # path literal
KELLY_MAX = 0.5   # thresholds.yaml 의 sizing.kelly_cap 와 중복 선언
```

✅ 올바름
```python
from infrastructure._common.utils import load_env_file, load_thresholds, audit_dir
env = load_env_file()                  # .env 경로는 utils 가 캡슐화
cache = audit_dir() / "_nav_cache"     # path literal 대신 path helper
kelly_cap = load_thresholds()["sizing"]["kelly_cap"]
```

**Hook**: 자동 path-literal 차단 hook 은 제거됨 (구 `block_path_literals` / `doctrine_lint`). thresholds 중복 선언·경로 literal 은 PR/리뷰 시 인용. 경로는 `infrastructure/_common/utils.py` 의 path helper (`trail_dir` / `audit_dir` / `positions_dir` 등) 로 얻는다.

---

## D-CORE-2 — KISS (사소한 가지치기 금지)

**근거**: 본 시스템의 default 는 "아무 것도 하지 않음". 가설적 미래 요구에 대비한 추상화는 도메인 룰(생존 우선)과 충돌. 비슷한 코드 3 줄은 추상화보다 낫다.

❌ 금지
```python
class AbstractCatalystStrategyFactory(ABC):
    @abstractmethod
    def build(self, regime: str, ticker: str, lookback: int) -> "BaseCatalyst": ...
# (실제 사용처는 단 한 곳, 한 종류)
```

✅ 올바름
```python
def scan_buyback_catalyst(regime: str, ticker: str) -> dict[str, Any]:
    """단일 caller, 단일 catalyst 종류 — 직접 함수로 표현."""
    ...
```

**Hook**: `inject_only` (PostToolUse 자동 검사 어려움 — code review 시 인용).

---

## D-CORE-3 — Default No-Action

**근거**: 매일 새 후보 0, 보유 포지션 thesis-breaking event 0, action required = None 이 정상. 새 시그널을 만들기 위해 코드를 작성하지 말 것. 산출물이 비어도 정상 — `validate_stage_inputs()` 가 envelope 만 확인하고 통과해야 한다.

❌ 금지
- "후보 0 이면 fallback 으로 random 종목 추가" 같은 자동 채움 로직
- "regime=unknown 인데 임시로 mid 로 가정" 같은 fail-open 분기

✅ 올바름
```python
if not candidates:
    emit_summary_line("stage3", verdict="no_action", reason="no_catalyst")
    return  # 빈 envelope JSON 산출
```

**Hook**: `lint_directives.sh` (M2) — fallback / default 키워드 매핑 audit.

---

## D-CORE-4 — 모듈 경계 (DDD bounded contexts)

**근거**: `$DOMAINS_DIR` (행정부) ↔ `$INFRA_COMMON_DIR` 외 infra (외부 I/O) ↔ `$GOVERNANCE_DIR` (입법부) ↔ `$OPERATIONS_DIR` (산출물) 의 4 layer 가 단방향 의존. 위반 시 hook / skill / config 가 서로를 호출하게 되어 회귀 영향이 폭발.

✅ 의존 방향
```
governance        ←── (read-only) ── 모든 layer
infrastructure    ←── domains (read)
domains           ←── operations 산출만 write
.claude/hooks     ←── infrastructure._common (utils), 절대 도메인 코드 import 안 함
.claude/skills    ←── governance 만 read, 직접 도메인 코드 작성 안 함
```

❌ 금지: `$INFRA_DART_DIR/client.py` 에서 `domains.universe.main` import. infrastructure → domains 역방향.

**Hook**: `block_anti_patterns.sh` (PreToolUse) — D-CORE-4-A 위반(`from domains` in infra layer) regex 차단.

---

## D-CORE-5 — 의존성 최소화 (`pyproject.toml` 기반)

**근거**: 새 third-party 의존 추가는 보안 surface 확대 + 빌드 복잡도. stdlib 또는 기존 의존(`PyYAML`, `requests`) 으로 가능하면 추가 금지.

✅ 절차
1. 기존 의존으로 가능한지 검토 (`grep -r "import .*PyYAML\|requests" $DOMAINS_DIR`)
2. 추가가 정말 필요하면 `pyproject.toml` 의 `dependencies` 또는 `[project.optional-dependencies]` 에 명시
3. version 핀 (`requests>=2.31,<3`) — `>=` 만 적지 말고 major 캡

**Hook**: `inject_only` (PostToolUse 자동 검사 어려움 — PR/리뷰 시 인용).

---

## D-CORE-6 — 작업 직전 read, 변경 직후 verify

**근거**: agent 가 SSoT 와 실제 코드 사이 drift 를 만드는 가장 흔한 원인은 "기억에 의존한 작성". 본 시스템은 SessionStart hook 이 alias / trail / 포지션 컨텍스트를 매번 inject 하니, 그 컨텍스트를 신뢰하고 read 한 후에 작성하라.

✅ 룰
- 새 helper 작성 전: 같은 도메인의 기존 helper 1 개를 Read (import 순서 / typing 패턴 모사용)
- config 수정 전: 해당 yaml 파일 전체 Read (들여쓰기 / 주석 density 보존)
- 작성 직후: 관련 `pytest` 1 회 실행 (또는 최소한 import 확인) — drift 즉시 검출

**Hook**: `lint_directives.sh` (PostToolUse) — Write/Edit 직후 directive 검사 (`_directive_lint.py`, M1 dry-run).

## D-CORE-7 — LLM 호출은 단일 port, vendor 종속은 bounded adapter (F-13)

**근거**: LLM 종속은 (A)모델·(B)SDK·(C)런타임 3층 중 **(C)런타임(`claude -p` CLI) 한 층뿐**이며 얇고 contained 다 (Anthropic SDK/API import 0, 모델명 하드코딩 0). 이 얇은 종속을 한 곳에 모아두면 vendor 교체가 "adapter 1 클래스" 작업으로 끝난다. `claude -p "/skill"` 은 single completion 이 아니라 **agentic loop** (도구·파일·다단계) — raw model API 로 대체 불가, 대체 vendor 도 agentic harness 여야 한다. 현실 타깃은 "swap 을 bounded adapter 작업으로", "지금 vendor-free" 가 아니다.

✅ 룰
- LLM 런타임 호출은 `infrastructure/llm` dispatcher 경유 (`python -m infrastructure.llm.dispatcher`) — `notify` dispatcher 와 동형. 새 vendor = `LlmAdapter` 1 클래스 + REGISTRY 한 줄.
- **SKILL.md 본문 = portable 자산** (모델 비종속 지시), **frontmatter / tool 이름 = 바인딩** (harness 별 조정 지점). 본문에 vendor/harness 고유 가정 박지 말 것.
- **가드 = portable Python** (`domains/` · `infrastructure._common`), **훅 = thin marshaling** (stdin→env, exit code). 가드 로직을 훅 셸에 박으면 harness 교체 시 enforcement 가 깨진다.
- 모든 LLM↔결정론 경계는 JSON schema envelope (D-Q-2) 로 gate — vendor-neutral seam.

❌ 안티패턴: 새 스크립트에서 `claude -p` 를 직접 호출 / `import anthropic` 도입 / 모델명 하드코딩 / 결정론 산수를 LLM 에 위임 (G6).

**Hook**: inject_only (`inject_directive_context.sh`) — 아키텍처 불변식이라 syntactic 자동 검사 없음. PR/리뷰 시 인용.
