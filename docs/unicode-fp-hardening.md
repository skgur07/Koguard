# PF-012 Unicode·오탐 hardening 보고서

- 측정일: 2026-08-14
- 환경: Windows, CPython 3.11.9
- 정책: 등록 term과 승인 변형은 문맥과 무관한 positive이며 Whitelist만 명시적으로 보호한다.
- 공개 회귀 자료: `tests/corpus/unicode_fp_cases.json` 20건

## 변경한 경계

정규화기는 Unicode category `Cf`인 보이지 않는 format character가 등록 term을 분리하지
못하게 한다. 한글 음절이나 자모 바로 뒤의 combining mark와 variation selector도 탐지용
정규화 view에서 무시한다. NFKC가 서로 다른 원문 cluster에서 만든 canonical Hangul jamo는
전체 view에서 한 번 더 조합한다.

제거한 code point 자체를 임의의 한글로 치환하지 않는다. 정규화된 각 문자는 여전히 기여한
원문의 `[start, end)`를 보존하므로, 내부에 제거 문자가 있던 매치는 첫 글자부터 마지막 글자까지
원문 전체 구간을 가리킨다. 한글 뒤의 trailing combining mark도 직전 문자의 span에 포함한다.
Whitelist도 같은 view와 원문 구간을 사용한다.

## 정확도 전후 비교

| slice | 수정 전 | 수정 후 |
| --- | ---: | ---: |
| format positive | TP 0 / FN 5 | TP 5 / FN 0 |
| combining positive | TP 0 / FN 2 | TP 2 / FN 0 |
| compatibility positive | TP 1 / FN 1 | TP 2 / FN 0 |
| Unicode 다중 매치 | TP 0 / FN 2 | TP 2 / FN 0 |
| Whitelist override | TP 1 / FN 0, exact case 2/2 | TP 1 / FN 0, exact case 2/2 |
| 정책 hard-negative | FP 0, exact case 8/8 | FP 0, exact case 8/8 |
| 전체 | TP 2 / FP 0 / FN 10, exact case 11/20 | TP 12 / FP 0 / FN 0, exact case 20/20 |

이 표의 FP는 등록 term이나 승인 변형이 없는 입력에서 생긴 탐지만 뜻한다. `시발점`처럼 등록
term을 실제로 포함한 문자열은 제품 정책상 false-positive로 재분류하지 않는다.

## 최대 입력 성능

공개 기본값인 `balanced` profile을 동일 프로세스에서 각 100회, warmup 10회 측정했다. 모든
입력은 기본 최대 길이 4,096자다. 메모리는 `tracemalloc`의 한 번의 `check()` peak Python
allocation이며 RSS나 native allocation은 포함하지 않는다.

| workload | 수정 전 p95 | 수정 후 p95 | 수정 전 peak | 수정 후 peak | 수정 후 탐지 |
| --- | ---: | ---: | ---: | ---: | ---: |
| format-only | 23.5186ms | 1.0235ms | 782,062 B | 13,319 B | 0 |
| format interleaved clean | 15.1161ms | 4.4164ms | 782,062 B | 338,838 B | 0 |
| format-obfuscated positive | 25.3115ms | 1.0997ms | 781,930 B | 14,079 B | 1 |
| combining-obfuscated positive | 10.4186ms | 12.1432ms | 2,499,676 B | 2,499,860 B | 1 |

PF-009에서 정한 최대 입력 p95 임시 예산 15ms를 네 workload가 모두 통과한다. 최악 결합문자
입력의 peak allocation 증가는 184 bytes이며, 기존 선형 정규화 상한을 유지한다. 원시 결과는
`evaluation/results/pf012-before-windows-python311.json`과
`evaluation/results/pf012-after-windows-python311.json`에 기록한다.

## 통과 기준

- 공개 positive occurrence FN 0
- 정책 hard-negative FP 0
- 원문 span과 결정적 매치 순서 불일치 0
- format 문자가 포함된 Whitelist 보호 위반 0
- 4,096자 적대 입력 p95 15ms 이하
- 입력 길이 제한과 기존 선형 combining-cluster 작업량 계약 유지

## 알려진 한계

- 20건은 공개 결정적 회귀 corpus이지 독립 hidden 실서비스 corpus의 대체물이 아니다.
- 키릴 문자처럼 모양만 비슷한 homoglyph를 한글로 치환하지 않는다.
- 보이는 구두점과 공백은 format character가 아니며 해당 matcher가 활성화된 profile에서만
  우회 표현으로 처리한다.
- combining mark 제거는 한글에 붙은 경우로 제한한다. 다른 문자 체계는 표준 NFC/NFKC 의미를
  유지한다.
- `Cf`는 화면상 의미가 있는 bidi control이나 emoji ZWJ도 포함한다. Koguard의 lexical 차단
  정책에서는 이를 보이지 않는 term 분리자로 인정하지 않지만, 사용자에게 반환하는 원문과
  match span은 변경하지 않는다.

## 재현

```powershell
uv run pytest tests/test_normalizer.py tests/test_unicode_hardening.py
uv run python -m evaluation.unicode_hardening_report `
  --iterations 100 `
  --warmups 10 `
  --output evaluation/results/pf012-local.json
```
