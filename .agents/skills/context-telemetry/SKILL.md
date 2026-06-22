---
name: context-telemetry
description: telemetry/ 파일 읽기/쓰기/정리 전 반드시 로드. 미로드 시 retention·보존·G20(덮어쓰기 금지)·산출물 레이아웃 규칙 위반 확정. 새 산출물 종류 추가 전에도 필수.
---

# context-telemetry

`telemetry/` 디렉토리(파이프라인의 cross-day 누적 증거 스토어) 작업 전 invoke. 본문은 인덱스 —
상세는 `common/` 파일 참조.

> `telemetry/` 는 **재생성-불가 증거 + cross-day 상태**의 루트다 (ADR-0008). `operations/{date}/`
> (일별 휘발·재생성 가능)·`.cache/`(재생성 가능)·`config/`(사용자 입력)·`secrets/`(자격증명)와
> 분류축이 다르다. 산출물 종류의 단일 진실원천(SSoT)은
> `infrastructure/_common/telemetry_registry.py` 의 `REGISTRY` 다.

## 선행 읽기 (common/)

1. `common/overview.md` — telemetry/ 전체 트리 + subdir별 역할/생산자/git 추적 여부.
2. `common/retention-classes.md` — 5 보존 클래스(PERMANENT/STATE/SNAPSHOT/BINARY/EPHEMERAL) +
   retention GC 의 stale/legacy 3단계 판정 로직 + `make telemetry-gc` 사용법.
3. `common/artifact-registry.md` — `REGISTRY` kind 표 (kind ↔ glob ↔ retention ↔ producer).
   신 산출물 추가 시 등록 절차.
4. `common/positions-store.md` — `telemetry/positions/` 스토어 계약 (`_account/` 계보 +
   per-ticker thesis state). 구 `positions/README.md` 흡수.
5. `common/audit-layout.md` — `telemetry/audit/` concern별 subdir 레이아웃.

## 핵심 불변식

- **SSoT = REGISTRY**: telemetry 에 체계적으로 저장되는 모든 산출물 종류는
  `telemetry_registry.REGISTRY` 에 등록된다. 미등록 파일은 GC 가 ORPHAN 으로 본다
  (arch 테스트 `test_live_telemetry_has_no_orphans` 가 드리프트를 red 로 만든다).
- **경로는 path helper 경유** (`infrastructure/_common/utils.py`): `telemetry_dir` /
  `audit_dir` / `positions_dir` / `positions_account_dir` / `nav_history_dir` /
  `external_signal_intake_dir` / `policy_drafts_dir` / `segment_vector_store_path`.
  env override seam (`$TELEMETRY_DIR` 등) = 테스트/cron 격리.
- **G20 (덮어쓰기 금지)**: writer 는 `write_output_safely` 경유 — 충돌 시 `.{N}` suffix.
  사후 `.{N}` 충돌본은 retention class 와 무관하게 GC 가 최신본만 canonical 로 정규화한다
  (`.gitignore` 가 `telemetry/**/*.[0-9]*.{ext}` 를 untrack — 충돌본은 transient).
- **삭제 = 증거 소실** (ADR-0008): PERMANENT/STATE/BINARY 는 GC 가 prune 하지 않는다. SNAPSHOT
  만 (kind, scope)별 최신 1건 유지. 생산자 소멸/포맷 위반(ORPHAN·LEGACY)만 삭제.

## retention GC

```bash
make telemetry-gc          # dry-run (계획만 출력, 변경 없음)
make telemetry-gc-apply    # 실제 삭제/정규화 (PERMANENT/STATE/BINARY 불변)
python -m applications.telemetry_gc --keep-logs-days 30 --apply   # EPHEMERAL age-prune
```

판정 로직 3단계 (상세 `common/retention-classes.md`): ① LEGACY/ORPHAN(생산자 소멸·미등록·
id_validator 위반) → 삭제 ② SNAPSHOT supersession((kind,scope)별 최신 1건) ③ COLLISION-DUP
(`.{N}` 최신본만 canonical 로 정규화).

## 전형적 실패 패턴

- **새 산출물을 REGISTRY 미등록 채로 telemetry 에 write** → arch 테스트 red. 먼저 kind 등록.
- **ticker dir 을 bare 6-digit(`088350`)으로 생성** → `id_validator(^KR_\d+$)` 위반 → ORPHAN.
  콜론 sanitize 규약 `KR:003550 → KR_003550` 준수 (`positions`/`nav-history`/`external_signals`/
  `policy_drafts` 공통).
- **append-only 증거(nav-history/violations/external_signals)를 날짜별 스냅샷처럼 prune** → 금지.
  PERMANENT.
- **path 를 helper 우회해 하드코딩** → env override seam 깨짐 (테스트 격리 실패).

## Out of Scope

- `operations/{date}/` 일별 trail 산출 — 휘발·재생성 가능 (telemetry 아님).
- `.cache/` (DART corp index 등 재생성 가능 캐시) — 언제든 삭제 가능.
- `config/signals/` (사용자 입력 breadth) — telemetry/external_signals(ingest 증거)와 구분.
- 각 BC 도메인 로직 — 해당 `context-{bc}` 스킬 참조 (본 스킬은 산출물 스토어 계약만).
