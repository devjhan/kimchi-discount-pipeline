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

**Hook**: `block_anti_patterns.sh` (PreToolUse) — secret-like 정규식 (prefix-bound, ≥8 자) 매치 시 exit 2. false positive 시 `INVEST_SEC_GUARD_OFF=1` 로 우회.

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

**Hook**: `pre_env_guard.sh` (기존, PreToolUse Read|Bash|Write|Edit) — `$ENV_PATH` 직접 접근 차단.

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

**Hook**: `$SETTINGS_PATH` 의 `permissions.deny` (1차 방어) + `pre_no_autotrade.py` (M2 예정).

---

## D-SEC-4 — alias-only path (D-CORE-1 의 security 측면)

**근거**: 사용자 machine 절대경로가 본문에 등장하면 환경 leak + 다른 사용자 환경에서 reproducibility 깨짐. 모든 path 는 alias 경유.

<!-- legacy-ok -->
❌ 금지 (의도적 anti-pattern 예시)
```python
state = Path("/Users/me/projects/investment_v3/operations/_audit/state.json")
```
<!-- /legacy-ok -->

✅ 올바름
```python
state = Path(os.environ["AUDIT_DIR"]) / "state.json"
```

**Hook**: `block_path_literals.sh` (기존, PreToolUse Write/Edit) — 절대경로 + 상대경로 prefix 두 종 차단.

---

## D-SEC-5 — 외부 신호 ingest 는 명시 명령으로만

**근거**: 뉴스 / 트윗 / 블로그 / 리포트 / 사용자 prompt 의 외부 의견이 thesis 를 즉시 변경하면 confirmation bias 의 자동화. 명시적 `/ingest-external-signal` 명령으로만 ingest, 즉시 thesis 변경 안 함 (다음 cron run 의 Stage 4 thesis-auditor 가 fact-only 인용).

❌ 금지: 사용자 prompt 본문에 "뉴스 X 가 종목 Y 의 thesis 를 깬다" → 직접 `04-thesis-candidates.json` 수정.

✅ 올바름:
1. `/ingest-external-signal` 으로 raw payload paraphrase + redact 후 `$EXTERNAL_SIGNALS_DIR/{ticker}/{date}-{seq}.md` 저장
2. 다음 cron run 의 Stage 4 가 fact-only 인용

**Hook**: `inject_only` — bootstrap.md §1 (Source of Truth Hierarchy) 가 SessionStart 에 inject 됨.

---

## D-SEC-6 — `$AUDIT_DIR/_hook_audit.log` 는 본문에 secret 절대 echo 안 함

**근거**: hook telemetry log 가 git tracked 가능 (사용자 결정). 따라서 log line 의 `{reason}` 필드에 secret 변수 echo 금지. `_audit_log("BLOCK", f"detected KIS_APP_KEY in payload")` 같이 *변수 이름만* 인용, 값 인용 안 함.

❌ 금지
```python
_audit_log("BLOCK", f"secret leak in line: {leaked_line}")   # leaked_line 에 secret 통째 포함
```

✅ 올바름
```python
_audit_log("BLOCK", f"secret-like pattern at line {ln}, type=KIS_APP_KEY")  # 위치 + 타입만
```

**Hook**: `lint_directives.sh` (PostToolUse, M2) — `_audit_log(...)` 두 번째 인자에 secret-like literal 직접 인용 검사.
