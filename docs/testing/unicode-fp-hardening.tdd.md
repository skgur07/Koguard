# PF-012 Unicode·오탐 hardening TDD 증거

## RED

공개 corpus와 정규화 unit test를 먼저 추가했다. 수정 전에는 targeted 40건 중 5건이 실패했다.

- `시\u200b발`, `시\u200d발`, word joiner, BOM, bidi override를 Exact가 놓쳤다.
- `시\u0301발`과 variation selector 삽입을 놓쳤다.
- NFKC의 `㉦ㅣ`가 canonical jamo `시`에서 `시`로 다시 조합되지 않았다.
- 수정 전 공개 corpus 집계는 TP 2, FP 0, FN 10, exact case 11/20이었다.
- `balanced` format-only 최대 입력 p95는 23.5186ms였고 format-obfuscated positive는
  탐지하지 못했다.

## GREEN

- category `Cf`를 정규화 view에서 선형으로 건너뛴다.
- 한글 바로 뒤의 combining mark와 variation selector만 제거한다.
- cluster별 NFKC 뒤 canonical jamo가 남은 드문 경로만 전체 view에서 재조합한다.
- 재조합된 문자 span은 decomposition origin을 기존 원문 span으로 합성한다.
- public corpus 20/20 exact, TP 12, FP 0, FN 0을 달성했다.
- 최대 입력 네 workload의 p95가 모두 15ms 이하이며 정답 match count도 함께 기록된다.

## 회귀 계약

| 계약 | 테스트 |
| --- | --- |
| format character를 건너뛰고 원문 span을 보존 | `test_normalizer_ignores_format_character_inside_hangul_term` |
| 한글 결합 확장 문자를 제거하고 span을 보존 | `test_normalizer_ignores_combining_extension_inside_hangul_term` |
| 서로 다른 NFKC cluster의 자모를 재조합 | `test_normalizer_recomposes_nfkc_jamo_across_source_clusters` |
| format-only 최대 입력이 Unicode slow path를 사용하지 않음 | `test_normalizer_ignores_format_only_maximum_input_without_slow_path` |
| slice·Whitelist·다중 매치·hard-negative 계약 | `test_unicode_fp_corpus_preserves_policy_spans_and_whitelist` |
| p50·p95·peak memory를 재현 가능한 JSON으로 기록 | `test_unicode_hardening_report_records_accuracy_latency_and_memory` |

## 근거 artifact

- 공개 회귀: `tests/corpus/unicode_fp_cases.json`
- 수정 전: `evaluation/results/pf012-before-windows-python311.json`
- 수정 후: `evaluation/results/pf012-after-windows-python311.json`
- 해석과 한계: `docs/unicode-fp-hardening.md`
