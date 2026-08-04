# 탐지 단계 기본 활성화 TDD 기록

작성일: 2026-08-04

## 목표

현재 구현된 탐지 단계는 모두 기본으로 실행하되, 사용자가 각 단계를 정확한 `bool` 설정으로
독립적으로 끌 수 있게 한다. 기존 `EngineConfig`의 앞 일곱 위치 인자 순서는 유지한다.

## 공개 계약

| 설정 | 기본값 | `False`일 때 |
| --- | --- | --- |
| `exact_matching` | `True` | 정규화된 Exact Match를 실행하지 않는다 |
| `repeated_matching` | `True` | 반복 축약 view를 만들거나 검색하지 않는다 |
| `separator_matching` | `True` | 구분자 제거 view를 만들거나 검색하지 않는다 |
| `whitespace_gap_matching` | `True` | 공백·탭 전용 매칭과 해당 trie 생성을 끈다 |
| `mixed_gap_matching` | `True` | 공백·구분자 혼합 매칭과 해당 automaton 생성을 끈다 |
| `choseong_matching` | `True` | 초성 index 생성과 초성 검색을 끈다 |

`whitespace_gap_matching`과 `mixed_gap_matching`은 서로 독립적이며, 두 단계 모두
`max_whitespace_gap`을 공백 구간 상한으로 사용한다. 여섯 설정에는 `1`, 문자열, `None` 같은
유사 참값을 허용하지 않는다.

## RED

- 기본값, 여섯 단계의 개별 비활성화, 공백·혼합 독립성, 벤치마크 `minimal` profile을 먼저
  테스트로 추가했다.
- 결과: 47개 수집 중 23개 실패, 24개 통과.
- 실패 원인은 공백·초성의 기존 `False` 기본값, 존재하지 않는 네 설정 필드, 기존 엔진의
  무조건 실행 경로, 존재하지 않는 `minimal` profile이었다.

## GREEN

- `EngineConfig`에 여섯 개의 기본 활성화 플래그와 엄격한 `bool` 검증을 적용했다.
- 엔진이 비활성화된 반복·구분자 view와 각 매칭 단계를 건너뛰도록 분기했다.
- 공백 trie와 혼합 automaton의 생성 조건을 분리했다.
- 벤치마크에 Exact Match만 사용하는 `minimal` profile을 추가하고 기능별 profile을 격리했다.
- 핵심 계약 테스트: 49개 통과.
- 관련 설정·엔진·매처·벤치마크 테스트: 기준선 재생성 전 192개 통과, 예상된 기존 기준선
  지문 불일치 1개.

## 후속 관계

다음 문서는 각 기능을 처음 추가했을 당시의 opt-in 설계와 RED/GREEN 근거를 보존한다. 현재
기본값과 독립 설정 계약은 이 문서가 우선한다.

- `whitespace-gap-matching.tdd.md`
- `mixed-gap-matching.tdd.md`
- `choseong-matching.tdd.md`
