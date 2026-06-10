# Deployment Residency Spec

`schema: investment-deployment-residency-v1`
`last_updated: 2026-05-13`

## 1. 원칙

한국 금융 API (DART OPEN API, KIS Open Trading API, KRX data endpoints) 는
non-Korean / cloud-datacenter IP 를 차단한다. 차단 형태는 기관별로 상이하나,
**해외/클라우드 IP 에서는 인증 / 데이터 조회 자체가 불가능**하다는 결론은
동일하다.

| 기관 | 클라우드 IP 응답 (관측 2026-05-12 ~ 2026-05-13) | 로컬 KR ISP 응답 |
|---|---|---|
| DART (FSS) `opendart.fss.or.kr/api/list.json` | HTTP 503 (WAF 거부) | HTTP 200 status=000 |
| KIS `openapi.koreainvestment.com:9443/oauth2/tokenP` | socket timeout (TCP 차단) | 토큰 0.2초 발급 |
| KRX `data.krx.co.kr/.../getJsonData.cmd` | HTTP 403 (명시적 거부) | (정상으로 추정) |

KIS 공식 FAQ ("별도 허용 IP 목록 운영하지 않음") 은 **국내 개인 IP 차단 부정**
이지, 해외/클라우드 데이터센터 IP 차단까지 부정하지 않는다. FAQ 와 본 spec
은 모순이 아니다.

## 2. Primary deployment

로컬 macOS (`launchd`) 또는 Linux (`systemd --user`) 환경에서 **Korean
residential ISP** 망 경유로 실행한다. 스케줄의 단일 SSoT 는
<!-- legacy-ok -->`governance/schedules.yaml`<!-- /legacy-ok -->. OS 별
artifact 는 <!-- legacy-ok -->`infrastructure/scheduling/*_generator.py`<!--
/legacy-ok --> 가 derived 결과로 emit 한다.

본 spec 채택일 (2026-05-13) 기준 v1 에서는 macOS launchd 만 generator 가
구현됨. systemd / Windows 는 v2 후보.

## 3. Fallback deployment (제한적 허용)

Cloud LLM (claude-code-era, 현재 비활성) 실행은 다음 조건 **모두** 만족 시에만
허용된다:

1. 해당 stage 가 KIS / DART / KRX 어떤 endpoint 도 호출하지 않음
2. 사용 API 가 Yahoo Finance / FRED 등 **IP residency 무관 출처만**
3. 산출물 본문 / 로그가 클라우드 worktree 에 남아도 secret 유출이 없음 (G21 정합)

위 조건을 1개라도 미충족하는 stage 의 cloud 실행은 G9 (graceful-fail 위반)
및 본 spec 의 위반이다. 위반 발견 시 audit-process skill 의 weekly finding
으로 노출.

현재 (2026-05-13) cloud routine 의 daily 실행은 위 조건을 모두 위반 (DART/KIS
호출) 하므로 **사실상 비활성** 상태다. `applications/cloud_routine_run.sh` 는
deprecated 처리되었으며, 첫 줄에서 즉시 `exit 1` 로 차단된다.

## 4. 결정 우선순위

본 spec 은 AGENTS.md / 모든 deployment 관련 결정의 상위에 위치한다. 모순 발생
시 본 spec 이 우선한다. 본 spec 의 개정은 governance layer 의 commit +
audit-process review 가 동반된다.

## 5. 재활성 조건 (cloud routine 부활)

본 spec 의 §3 조건을 모두 만족하는 신규 cloud stage 도입 또는 KIS / DART /
KRX 의 IP 정책 변경 (공식 공지 또는 재테스트로 확인) 이 있을 때 deprecation
헤더 제거 + registry entry 의 `retain: true` → `retired: <date>` 전환으로
활성화 가능. 이때 <!-- legacy-ok -->`infrastructure/scheduling/install.sh`
<!-- /legacy-ok --> 의 OS 분기에 cloud target 옵션 추가를 권장.

## 6. 참조

- `governance/schedules.yaml` — 스케줄 SSoT
- `AGENTS.md` G9 — auto-trade 금지 (본 spec 과 상호 정합)
- `applications/run_daily_local.sh` — primary deployment 의 단일 진입점
