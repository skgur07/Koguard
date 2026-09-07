# 평가 corpus와 측정 harness TDD 증거

## 사용자 여정

Koguard 유지보수자는 사전이나 matcher를 바꾸기 전에, 그 변경이 탐지율과 오탐에 어떤
영향을 주는지 재현 가능한 수치로 확인할 수 있어야 한다. 지금까지는 기능별 회귀 corpus만
있어 "정상 문장을 얼마나 잘못 잡는지"를 측정할 수단이 없었다.

## 범위

[제품 집중 계획](../product-focus-plan.md)의 PF-001(corpus schema와 annotation guide),
PF-004(tuning/evaluation 분리), PF-005(대조군 corpus)의 축소판, PF-003(matcher ablation)을
구현한다. PF-007 사전 확장은 이 측정 기반이 생긴 뒤에 진행한다.

## RED

- 테스트: `tests/test_evaluation_corpus.py`
- 명령: `uv run pytest tests/test_evaluation_corpus.py --no-cov -q`
- 결과: `evaluation.loader` 부재로 collection error

## GREEN

- `evaluation/schema.py`: 계획 §6.3 스키마와 slice 정의
- `evaluation/loader.py`: 스키마 검증, id 중복 차단, span 무결성, split 누출 차단
- `evaluation/report.py`: occurrence·문장 지표, 정상 문장 FP rate, slice별 집계
- `evaluation/koguard_runner.py`: Koguard 어댑터와 leave-one-out ablation
- `evaluation/corpus/`: 166개 케이스 (hard negative 122, positive 40, review 4)
- 명령: `uv run pytest tests/test_evaluation_corpus.py --no-cov -q`
- 결과: `10 passed`

## 구현 중 발견해 수정한 계약 결함

Validator가 `pos-rep-01`(`시이이발` → `시발`)을 거부했다. span이 canonical term을 문자열로
포함해야 한다는 최초 불변조건이 우회 표기에서는 성립하지 않는다. `OBFUSCATION_SLICES`를
도입해 해당 slice에서만 문자열 대응 검사를 건너뛰도록 규칙을 좁혔다.

## 전체 검증

- `uv run ruff format --check .`: 통과
- `uv run ruff check .`: 통과
- `uv run mypy`: 32개 source file, 오류 없음
- `uv run pytest`: `424 passed`, branch coverage `95.59%`

## 보장 동작

| # | 보장 내용 | 검증 |
| --- | --- | --- |
| 1 | 모든 케이스가 문서화된 스키마로 파싱된다 | `test_every_case_parses_into_the_documented_schema` |
| 2 | case id가 split 전체에서 고유하다 | `test_case_ids_are_unique_across_every_split` |
| 3 | tuning과 evaluation이 같은 본문을 공유하지 않는다 | `test_tuning_and_evaluation_splits_do_not_leak_the_same_text` |
| 4 | span이 본문 범위 안에 있다 | `test_expected_match_spans_agree_with_the_case_text` |
| 5 | hard negative는 기대 매치를 선언하지 않는다 | `test_hard_negative_cases_declare_no_expected_match` |
| 6 | 필수 negative slice가 모두 존재한다 | `test_every_required_negative_slice_is_represented` |
| 7 | canonical term과 어긋난 span을 거부한다 | `test_validate_cases_rejects_a_span_that_does_not_match_its_canonical_term` |
| 8 | 중복 id를 거부한다 | `test_validate_cases_rejects_duplicate_ids` |
| 9 | review 케이스를 점수에서 빼되 개수는 보고한다 | `test_evaluate_cases_excludes_review_cases_but_reports_their_count` |
| 10 | 완전한 oracle이 1.0으로 채점된다 | `test_evaluate_cases_scores_a_perfect_oracle_at_one` |

## 알려진 제한

corpus 규모가 계획 §6.7의 목표(positive 500, negative 2,000)에 크게 못 미친다. 전 케이스가
`single_review`이며 직접 작성한 문장이다. 따라서 이 corpus의 수치는 구현 간 상대 비교와
회귀 감지에는 쓸 수 있지만, 실서비스 정확도를 대표한다고 주장할 수 없다.
