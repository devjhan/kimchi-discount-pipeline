# Retention Classes + Retention GC

telemetry 산출물은 ADR-0008("telemetry = 재생성-불가 증거")을 5 보존 클래스로 세분한다
(`infrastructure/_common/telemetry_registry.py` `RetentionClass`).

## 5 클래스

| Class | 의미 | 규칙 | 예 |
|---|---|---|---|
| **PERMANENT** | append-only 증거 — distinct date 전부 보존 | prune 안 함 (`.{N}` 정규화만) | nav-history, external_signals, violations/{bc}, breadth, subsidiaries, trade-log |
| **STATE** | living 단일 파일 (날짜 미박힘) | prune 안 함 (`.{N}` 정규화만) | thesis.json / thesis.md, shadow-portfolio/state.json |
| **SNAPSHOT** | point-in-time mirror/파생 | (kind, scope)별 **최신 1건**만 유지 | _account/summary·derived, balance, drift, expiry, scheduler-state |
| **BINARY** | 모델버전 의존 재생성-불가 바이너리 | 보존 | segments/vectors.sqlite |
| **EPHEMERAL** | 실행 로그 / commit 전 draft (gitignore) | `--keep-logs-days N` age-prune | logs/, policy_drafts/ |

> SNAPSHOT 의 "최신 1건"은 **상대적 supersession** — 절대 나이가 아니라 동일 (kind, scope)의
> 더 최신 date 가 존재하면 이전 것을 stale 로 본다. PERMANENT 는 날짜별 증거라 전부 보존.

## Retention GC — stale/legacy 판정 3단계

`infrastructure/_common/telemetry_gc.py` (순수 분류기+planner) + `applications/telemetry_gc.py` (실행기).

1. **LEGACY / ORPHAN** (생산자·포맷 축)
   - 파일이 어떤 `REGISTRY` kind glob 에도 매칭 안 됨 → **ORPHAN** (생산자 소멸 산출물 +
     미등록 신규 산출물. 예: ADR-0010 으로 파기된 hook 의 `logs/_hook_audit.log`).
   - kind 의 `id_validator` 위반 (예 ticker `088350` ∉ `^KR_\d+$`) → **ORPHAN**.
   - kind 의 `producer_module` 이 repo 에서 사라짐 → **LEGACY** (드리프트 가드).
   - → 전부 삭제.
2. **STALE** (SNAPSHOT supersession)
   - retention==SNAPSHOT kind 만. `(kind, scope)` 그룹 내 최신 date 1건 유지, 나머지 삭제.
3. **COLLISION-DUP** (`.{N}` 정규화, 모든 class 공통)
   - 같은 canonical 그룹의 `{base, .1, .2…}` 중 최신(max collision_n) 1개만 canonical 파일명으로
     정규화, 나머지 삭제. base 단독이면 그대로.
   - PERMANENT/STATE/BINARY 도 충돌본 정규화는 적용 (날짜 증거는 보존, 동일-날짜 재실행 중복만 제거).

결정론: 승자 = max collision_n (write_output_safely 가 base→.1→.2 순 기록 → 높은 N = 최신).
mtime 비의존.

## CLI

```bash
make telemetry-gc                                   # dry-run (기본, 변경 없음)
make telemetry-gc-apply                             # 실제 삭제/정규화
python -m applications.telemetry_gc --keep-logs-days 30 --apply
python -m applications.telemetry_gc --root /tmp/telemetry   # 루트 override(테스트)
```

기본 dry-run. `--apply` 명시해야만 FS 변경. 실행기는 delete → normalize 순서로 적용하고,
정리 후 빈 디렉토리를 제거한다 (`.gitkeep` 보유 디렉토리는 보존).

## 드리프트 가드

`tests/architecture/test_telemetry_registry.py::test_live_telemetry_has_no_orphans` 가 실제
telemetry/ 트리를 scan 해 ORPHAN/LEGACY 가 0 임을 단언한다. 신 산출물 종류를 REGISTRY 등록 없이
추가하면 red — "체계적으로 저장되지 않는 산출물" 재발 방지.
