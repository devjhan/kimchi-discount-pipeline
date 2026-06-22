# D-SEC — Security: secret / 하드코딩 / 자동매매 차단

자본 안전 + 정보 안전을 떠받치는 룰. G9 (자동매매 차단) / G21 (secret redact) 의 directive-tier 평면 인용.

---

## D-SEC-1 — secret-like literal 본문 매립 금지

**근거**: API key / token / 계좌번호 / passphrase 가 코드 / config / log / brief 본문 어디에도 raw 문자열로 등장하면 안 됨. `$ENV_PATH` (gitignore) 에서만 읽고, 출력 시 `secret_safe_log()` 가 redact.

❌ 금지 패턴 (정규식 sample, conservative — false positive 방지 위해 prefix-bound)
```
KIS_APP_KEY=PS[A-Za-z0-9]{20,}
KIS_APP_SECRET=[A-Za-z0-9+/]{30,}
DART_API_KEY=[a-f0-9]{40}
TELEGRAM_BOT_TOKEN=\d+:[A-Za-z0-9_-]{30,}
sk-[A-Za-z0-9]{32,}      # OpenAI / Anthropic-like
eyJ[A-Za-z0-9_-]{40,}    # JWT-like
```

❌ 금지 코드
```python
KIS_APP_KEY = "PSxxxxxxxxxxxxxxxxxxxxxxxx"   # 본문 매립
print(f"key={os.environ['KIS_APP_KEY']}")    # log 노출
```

✅ 올바름
```python
key = os.environ.get("KIS_APP_KEY")
if not key:
    raise SystemExit("[ERROR] KIS_APP_KEY missing in $ENV_PATH")
secret_safe_log("loaded KIS_APP_KEY", os.environ)  # 자동 redact
```

**Hook** (ADR-0010으로 파기: `block_anti_patterns.sh`): → 대체: ruff check + 수동 리뷰.

---

## D-SEC-2 — `$ENV_PATH` 직접 접근 금지 (Read/Bash/Write/Edit)

**근거**: 에이전트가 secret 파일을 직접 cat / read 하면 transcript 에 secret 잔존. 모든 secret 접근은 `os.environ` 경유 → `secret_safe_log()` 로 redact 된 form 만.

❌ 금지
```bash
cat .env
```

```python
text = Path(".env").read_text()
```

✅ 올바름
```python
key = os.environ.get("KIS_APP_KEY")  # SessionStart 가 이미 export
```

**Hook** (ADR-0010으로 파기: `pre_env_guard.sh`): → 대체: chmod 0600 + .gitignore로 OS 레벨 방어.

---

## D-SEC-3 — 자동매매 / 주문 호출 절대 금지 (G9 직역)

**근거**: 본 시스템은 regulatory + 실수 리스크 + agent autonomy 한계로 **체결 호출 절대 안 함**. KIS read-only whitelist (시세 read + 계좌 read) 외 KIS endpoint 호출 시 PreToolUse Bash deny.

❌ 금지 (`settings.json` permissions.deny 자동 차단):
```
*kis_order*
*place_order*
*TTTC0801U*       # 매수 endpoint
*TTTC0802U*       # 매도 endpoint
*TTTC0803U*       # 정정
*TTTC0851U*       # 취소
*CTSC0008U*       # 신용 주문
```

✅ 허용
```python
from infrastructure.kis.client import quote_price   # read-only whitelist
price = quote_price("005930")  # 시세 read OK
```

**Hook** (ADR-0010으로 파기: `.claude/settings.json` permissions.deny): → 대체: `runtime-policy.yaml` G9 + 코드 레벨 타입 안전성.

---

## D-SEC-4 — alias-only path (D-CORE-1 의 security 측면)

**근거**: 사용자 machine 절대경로가 본문에 등장하면 환경 leak + 다른 사용자 환경에서 reproducibility 깨짐. 모든 path 는 alias 경유.

❌ 금지 (의도적 anti-pattern 예시)
```python
state = Path("/Users/me/projects/kimchi-discount-pipeline/operations/_audit/state.json")
```

✅ 올바름
```python
state = Path(os.environ["AUDIT_DIR"]) / "state.json"
```

**Hook** (ADR-0010으로 파기: `block_path_literals.sh`): → 대체: ruff check + 수동 리뷰.

---

## D-SEC-5 — 외부 신호 ingest 는 명시 명령으로만

**근거**: 뉴스 / 트윗 / 블로그 / 리포트 / 사용자 prompt 의 외부 의견이 thesis 를 즉시 변경하면 confirmation bias 의 자동화. 명시적 `/ingest-external-signal` 명령으로만 ingest, 즉시 thesis 변경 안 함 (다음 cron run 의 Stage 4 thesis-auditor 가 fact-only 인용).

❌ 금지: 사용자 prompt 본문에 "뉴스 X 가 종목 Y 의 thesis 를 깬다" → 직접 `04-thesis-candidates.json` 수정.

✅ 올바름:
1. `/ingest-external-signal` 으로 raw payload paraphrase + redact 후 `$EXTERNAL_SIGNAL_INTAKE_DIR/{ticker}/{date}-{seq}.md` 저장
2. 다음 cron run 의 Stage 4 가 fact-only 인용

**Hook**: `inject_only` — bootstrap.md §1 (Source of Truth Hierarchy) 가 SessionStart 에 inject 됨.

---

## D-SEC-6 — 로그 내 secret-like literal 금지

**근거**: telemetry/logs 의 실행 로그에 secret 변수값 직접 등장 금지. 변수 이름만 인용, 값 인용 안 함.

❌ 금지
```python
log("BLOCK", f"secret leak in line: {leaked_line}")   # leaked_line 에 secret 통째 포함
```

✅ 올바름
```python
_audit_log("BLOCK", f"secret-like pattern at line {ln}, type=KIS_APP_KEY")  # 위치 + 타입만
```

**Hook** (ADR-0010으로 파기: `lint_directives.sh`): → 대체: 수동 리뷰.
