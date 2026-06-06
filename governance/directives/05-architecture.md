# D-ARCH — 아키텍처 / 배치 판단 기준

`$DIRECTIVES_DIR` 의 자매 파일. D-CORE(대원칙) 가 *코드 작성* 의 대원칙이라면, D-ARCH 는
**"무엇을 어디 두나 / 합칠까 쪼갤까 / 중앙이냐 분산이냐 / 이 결정 어떻게 남기나"** 라는
*구조 판단* 의 기준이다. 사용자가 "이 파일 위치/통폐합/중앙-분산이 적절한가" 를 매번
에이전트에 재질문하지 않고 **조회+적용** 할 수 있게 하는 룰 모음.

각 D-ARCH 는 구체 결정 사례를 [`../decisions/`](../decisions/README.md)(ADR) 로 cross-ref
한다 — 원칙(여기, 일반 룰) vs 결정(ADR, 구체 사례·대안)의 분업. D-CORE-4(모듈경계)·
D-CORE-7(LLM port) 은 그대로 두고, D-ARCH 가 그 위의 *판단 기준* 을 일반화한다.

> **Hook 주의.** D-ARCH 는 대부분 write-time hook 이 없다 (inject-only 또는 fitness test
> `tests/architecture/`). "모든 D-ID 에 PreToolUse/PostToolUse hook 이 있다" 는 가정은 D-ARCH
> 에 적용되지 않는다 — 구조 불변식은 syntactic per-file 검사가 아니라 repo-wide AST 검사라야
> 의미가 있기 때문 (`AGENTS.md` Hook 표 참조).

---

## D-ARCH-1 — 중앙 vs 분산 배치 = 소유/변경빈도/독자범위 축

**근거**: 분리축을 *파일 포맷* (yaml=config, md=doc) 으로 오인하면 잘못된 이동을 한다. 올바른
축은 **소유** (개발자 doctrine vs 사용자 override) · **변경빈도** · **독자범위** (cross-BC 헌법
vs BC 내부). 이 축을 잘못 잡으면 가드를 노브로 강등하는 보안 후퇴까지 발생한다.

❌ 금지
```
# "config 성이니까" governance/runtime-policy.yaml → config/ 로 이전
#  → G9 안전 enforcement 를 사용자 편집 가능 영역으로 강등 (보안 후퇴)
```

✅ 올바름
```
governance/   = git-tracked 개발자 doctrine (cross-BC·저빈도·헌법). md + machine-read yaml 동거 OK
config/ , *.local.yaml = gitignored 사용자/배포 override (deep-merge, local 우선)
domains/{bc}/.guidelines/ = BC 내부 HOW (코드와 함께 변함)
```

**Hook**: inject_only — 결정 사례 [ADR-0002](../decisions/0002-governance-config-ownership-axis.md) ·
[ADR-0008](../decisions/0008-storage-topology.md).

---

## D-ARCH-2 — 모듈 통/폐합 = CCP · CRP · SDP · ISP

**근거**: "합칠까 쪼갤까" 를 감으로 정하면 변경증폭(과병합) 또는 과분할이 된다. 명명된
컴포넌트 응집 기준으로 판단한다.

❌ 금지
```
# "한 파이프라인 연쇄" 라는 이유로 universe(enrich) + screener(cutoff) 수직 병합
#  → IO shape·타이밍·카디널리티가 다르고 함께 변하지 않음 = CCP 위반
```

✅ 올바름
```
CCP  함께 변하면 함께 산다 (변경축이 다르면 분리 유지)
CRP  함께 안 쓰는 것에 의존 강요 말 것 (단, 단일 정책 단위는 통째 의존이 ISP 정직 — ADR-0006)
SDP  안정성(불변) 방향으로 의존 (axioms/thresholds 는 depended-upon)
공통 관심사는 BC 병합이 아니라 _shared 로 hoist
```

**Hook**: inject_only — 결정 사례 [ADR-0004](../decisions/0004-bounded-context-split-criteria.md) ·
[ADR-0006](../decisions/0006-fat-contract-isp.md) · [ADR-0007](../decisions/0007-risk-engine-no-concern-reorg.md) (YAGNI / 맹목 지역화 금지).

---

## D-ARCH-3 — 의존 방향 단방향 불변식

**근거**: layer 의존이 양방향이 되면 hook/skill/config 가 서로를 호출해 회귀 영향이 폭발한다
(D-CORE-4 의 기계화). 4 layer 단방향: `governance ← (read) 모든 layer` · `infrastructure ←
domains` · `domains → operations write 만` · `application/domain 은 infra 직접 import 금지`.

❌ 금지
```python
# infrastructure/dart/client.py
from domains.universe.main import build         # infra → domains 역방향
# domains/screener/application/screen.py
from infrastructure.dart import client          # application 이 infra 직접 import
```

✅ 올바름
```python
# application/domain 은 주입받은 port 에만 의존; infra import 는 _boundary.py 만
def run(..., *, disclosure: DisclosureSourcePort) -> ...:
```

**Hook**: `block_anti_patterns.sh` (PreToolUse, `from domains` in infra regex) +
**fitness test** `tests/architecture/test_dependency_direction.py` · `test_boundary_gate.py`
(repo-wide AST, CI). 결정 사례 [ADR-0005](../decisions/0005-boundary-ports-and-adapters.md).

---

## D-ARCH-4 — 경계 / 포트 수명주기 (`_boundary` → typed adapter factory)

**근거**: 외부 의존을 BC 당 한 곳 (`_boundary.py`) 에 모으면 vendor 교체·테스트 stub·경계
강제가 쉬워진다. 그러나 그 한 곳이 path+time+citation+env+client 등 무관 concern 을 끌어안은
god-module(SPOF) 이 되면 ISP 위반·변경증폭. 좁은 Protocol port 로 추출한다.

❌ 금지
```
# _boundary.py 가 7 concern 을 한 fat 모듈로 (god-module / SPOF)
# 또는 _boundary 삭제하고 application 이 infra 직접 import
```

✅ 올바름
```
_boundary.py = typed adapter factory; 무관 concern 은 narrow port 로
  (CitationPort / ClockPort / DisclosureSourcePort / KisAccountPort)
main() composition root 가 port 를 구성해 application 에 주입
```

**Hook**: inject_only — HOW 템플릿은 `domains/screener/.guidelines/05-boundaries.md`
"Ports & Adapters" (복사 금지, 참조). 불변식 C/D 는 `test_boundary_gate.py` 가 검증. 결정
사례 [ADR-0005](../decisions/0005-boundary-ports-and-adapters.md) (선례 F-13 → D-CORE-7).

---

## D-ARCH-5 — per-BC 문서 표준

**근거**: BC 마다 문서가 들쭉날쭉하면 ("어디는 `AGENTS.md` 만, 어디는 `.guidelines/` 까지")
"이 문서 어디 두나" 에 답할 수 없다. 중앙(헌법)과 BC 산하(코드와 함께 변하는 HOW)를 일관
분담한다.

❌ 금지
```
# 새 BC 를 AGENTS.md 하나로만 (plugin 추가법·invariant·boundary 문서 누락)
# 또는 cross-BC 헌법을 한 BC 의 .guidelines/ 에 박음 (독자범위 오배치 — D-ARCH-1)
```

✅ 올바름
```
모든 BC = domains/{bc}/AGENTS.md            (외부 연결점 + 경계 grep + ADR 포인터)
        + domains/{bc}/.guidelines/00-overview .. 05  (plugin 추가법·invariant·boundary·audit·config-contract)
cross-BC 결정은 중앙 ADR / D-ARCH
```

**Hook**: **fitness test** `tests/architecture/test_doc_completeness.py` (`AGENTS.md` 7/7
+ `.guidelines/` 추적; 미충족 BC 는 `xfail` 로 명시 — silent cap 아님). 현재 `.guidelines/`
는 3/7 (macro·screener·universe); 나머지 4 BC 는 후속 채움 (xfail 이 추적).

---

## D-ARCH-6 — 구조 결정은 ADR 로 기록 (기각 포함) + 승격 경로

**근거**: 비자명한 구조 판단을 매번 에이전트에 재질문하면 답이 휘발·불일치한다. append-only
ADR 로 누적해 "조회+확장" 으로 전환한다. BC-local 패턴이 반복돼 cross-cutting 이 되면 중앙
D-ARCH/D-CORE 로 **승격** (선례 F-13 LLM port → D-CORE-7).

❌ 금지
```
# "이 파일 위치 적절?" 을 매 세션 에이전트에 새로 물음 (누적 0)
# 결정을 transient backlog(삭제 예정)에만 기록 → SSoT 소실
```

✅ 올바름
```
1. 기존 ADR 조회 (governance/decisions/)
2. 커버 안 되면 새 ADR 1장 (기각도 Rejected-proposal 로 영구)
3. 반복되는 BC-local 패턴 → D-ARCH 로 승격
```

**Hook**: inject_only — 트리거·템플릿은 [`../decisions/README.md`](../decisions/README.md).
`test_doc_completeness.py` 가 ADR 인덱스 무결성(모든 `NNNN-*.md` 가 README 링크) 검증.
