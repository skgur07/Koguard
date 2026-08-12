# PF-002 비교 러너 TDD 기록

## 목표

동일한 PF-001 gold corpus에서 Koguard와 고정된 Korcen 1.0.3 wheel을 재현 가능하게
평가하고, detector 기능 차이를 숨기지 않는 버전된 리포트를 만든다.

## RED

`tests/test_comparison_runner.py`를 먼저 추가했다. 구현 전에는
`ModuleNotFoundError: evaluation.comparison_runner`로 수집에 실패했다.

테스트가 고정한 계약은 다음과 같다.

- 닫힌 JSON Schema와 schema version 1
- artifact package/version/SHA-256 및 실행환경 기록
- detector별 실제 설정 기록과 설정을 포함한 configuration fingerprint
- sentence TP/FP/FN/TN, occurrence exact/span/canonical, slice 지표
- Korcen occurrence output의 명시적 `unsupported`
- `review` case 자동 평가 제외
- 원문과 canonical term의 리포트 비수록
- detector prediction과 gold annotation의 분리
- 동일 입력/configuration의 결정적 결과와 fingerprint
- Korcen 공식 wheel hash 불일치 거부
- worker case ID 누락·중복·추가와 capability 위반 거부
- 격리 worker의 UTF-8 stdin/stdout 고정

## GREEN

`evaluation/comparison_runner.py`에 corpus 로딩, wheel METADATA/hash 검증, 집계 지표,
버전된 리포트, CLI를 구현했다. `evaluation/detector_worker.py`는 각 detector를 별도
interpreter의 isolated mode로 실행하며 Koguard matcher 설정을 모두 명시한다.

Korcen은 boolean만 반환하므로 문장 지표만 계산한다. occurrence를 span이나 문자열
검색으로 추정하면 서로 다른 API를 같은 능력처럼 보이게 하므로 그렇게 하지 않는다.

## REFACTOR 및 검증 기준

- corpus 원문과 canonical term은 worker 요청과 메모리 내 계산에만 존재한다.
- 리포트와 오류에는 식별 가능한 본문을 기록하지 않는다.
- wheel filename만 신뢰하지 않고 content hash와 METADATA를 함께 검증한다.
- report ordering과 configuration fingerprint는 동일 입력에서 결정적이다.
- 단위 계약 외에 실제 built Koguard wheel과 공식 Korcen wheel로 CLI smoke test를
  수행한다.

실제 smoke test에서는 corpus 3건 중 `review` 1건을 제외한 2건이 평가되었고, Korcen
공식 wheel SHA-256과 설치 의존성 `better-profanity 0.7.0`, `colorama 0.4.6`이 리포트에
기록되었다. 생성된 JSON에 fixture 원문 및 gold canonical term이 포함되지 않는 것도
별도로 확인했다. 이 fixture의 크기는 정확도 비교 결론을 내리기에는 의도적으로 너무
작다.
