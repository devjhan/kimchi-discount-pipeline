# 4 Qualitative Lenses — stage2-quality-lens

`governance/policy/global/profiles/quality_floor.yaml` (screener RuleFactory 가 로드하는 global scope 정책) 의 `qualitative_lenses` 키.

---

## 1. Moat (산업 점유, 브랜드, 진입장벽)

평가 대상:
- 시장 점유율 (3년 추세)
- 브랜드 / 기술 / 네트워크 효과 / switching cost / 규모 경제
- 신규 진입자 출현 빈도

evidence 요구: helper의 financial cache + DART 사업보고서 본문 인용. 인용 없으면 `score='insufficient_evidence'`.

## 2. 자본배분 합리성 (소각 의지 / 재투자 ROI)

평가 대상:
- 자사주 매입 vs 소각 비율 (소각 priority)
- 배당 정책 일관성 (3~5년)
- M&A 가격 / 자회사 ROIC 변화
- 임원 보수 / 스톡옵션 dilution

evidence 요구: DART 자기주식 공시 + 배당 공시 + 분기보고서 자본 변동 표.

## 3. 회계 적신호 (영업CF vs 순이익 괴리, 충당금 패턴)

평가 대상:
- 영업CF / 순이익 ratio (3년)
- 매출채권 / 재고 회전일 변동
- 충당금 / 비영업 손익의 일회성 vs 반복성
- 감사의견 / 재고감사 history

evidence 요구: helper의 fcf_annual + revenue_recent + DART 감사보고서.

## 4. 지주사 자회사 산업 매력도 (지주사 한정)

평가 대상:
- 자회사 산업 cycle position
- 지분율 × 자회사 시총 join (helper의 NAV 캐시 활용)
- 자회사 IPO / 분할 가능성
- 지주사 discount 좁힘 catalyst presence

조건: ticker가 stage1 universe의 `source_category=holding_company` 인 경우에만 평가.
