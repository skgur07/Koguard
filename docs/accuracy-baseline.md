# Exact Match 정확도 기준선

측정일: 2026-07-27

대상: Koguard Exact Match + 사용자 주입 Whitelist

환경: CPython 3.11.9

## 결과

- 문장 수: 15
- 기대 탐지 occurrence: 16
- False Positive: 0
- False Negative: 0
- Precision: 1.0
- Recall: 1.0

## 범위

`tests/corpus/exact_cases.json`의 직접 작성한 최소 회귀 corpus를 사용했다. 단일·복수
Exact Match, 반복 매치, 반복 모음 우회, 정상 문장, 과거 기본 Whitelist 표현의 재분류,
확장된 기본 금칙어를 포함한다. 기본 Whitelist는 비어 있으며 사용자 주입 Whitelist의 구간
보호 동작은 별도 unit test로 검증한다.

이 결과는 구현 회귀를 감지하기 위한 초기 기준선이며 실제 서비스 환경의 정확도를
대표하지 않는다. 외부 데이터셋 검토 이후 corpus 규모와 표현 다양성을 확대하고 수치를
다시 측정한다.
