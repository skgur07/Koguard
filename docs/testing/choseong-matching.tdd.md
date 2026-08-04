# 초성 매칭 TDD 증거

## Source plan과 사용자 여정

별도 plan 파일 없이 이번 TDD 실행에서 요구사항을 확정했다.

- 사용자는 blacklist의 완성형 한글 표현으로부터 `ㅅㅂ`, `ㅆㅂ`, `ㄱㅅㄲ` 같은 초성 표현을
  탐지할 수 있다.
- 기본 설정 사용자는 새 오탐과 인덱스 비용 없이 기존 동작을 유지한다.
- 정상 한글 문장과 더 긴 초성·영숫자 토큰은 같은 초성을 가졌다는 이유만으로 탐지되지 않는다.
- 운영자는 초성 자체를 Whitelist에 넣어 실제 입력 구간을 보호할 수 있다.

## 공개 계약

- `EngineConfig.choseong_matching`의 기본값은 `False`이며 정확한 `bool`만 허용한다.
- 두 글자 이상의 완성형 한글 blacklist term만 초성 index에 포함한다.
- 입력의 일반 한글 음절은 초성으로 변환하지 않고, 명시적인 호환 자모 또는 현대 초성 자모
  연속열만 찾는다.
- 매치 양끝은 영숫자 토큰 경계여야 한다.
- 공백·구분자를 섞은 초성은 이번 범위에서 결합하지 않는다.
- 동일 초성 충돌은 dictionary의 결정적 정렬 순서로 canonical term 하나를 선택한다.
- 우선순위는 Exact, Repeated, Separator, Whitespace, Choseong, Mixed다.

## RED / GREEN 실행 증거

### 엔진 계약

- RED: `uv run pytest tests/test_config.py tests/test_models.py tests/test_engine.py -q`
  - 기존 테스트 142개 통과, 새 계약 22개 실패
  - 실패 원인은 없는 `choseong_matching`, `MatchMethod.CHOSEONG`, 초성 엔진 경로였다.
- GREEN: 같은 명령
  - `164 passed`, branch coverage 포함 전체 coverage `94.31%`

### 정확도 corpus와 benchmark 계약

- RED: `uv run pytest <초성 corpus 및 benchmark 4개 node id> -q --no-cov`
  - 초성 정확도 corpus 1개 통과
  - 없는 `choseong` engine profile, `choseong-scale` dictionary profile, benchmark corpus category로
    3개 실패
- GREEN: 같은 4개 node id 실행
  - `4 passed`

## 테스트 명세

| # | 보장 동작 | 테스트 | 종류 | 결과 |
|---|---|---|---|---|
| 1 | 기능은 기본 설정에서 꺼져 있다 | `test_choseong_matching_is_opt_in` | integration | PASS |
| 2 | `ㅅㅂ`, `ㅆㅂ`, `ㄱㅅㄲ`와 원문 span을 반환한다 | `test_choseong_matching_detects_standalone_initials_with_original_span` | integration | PASS |
| 3 | `수박` 같은 일반 한글을 초성으로 변환하지 않는다 | `test_choseong_matching_does_not_convert_normal_hangul_text` | regression | PASS |
| 4 | 더 긴 자모·숫자·한글 토큰의 일부를 거부한다 | `test_choseong_matching_rejects_partial_alphanumeric_tokens` | boundary | PASS |
| 5 | 명시적 초성 Whitelist가 겹치는 구간을 보호한다 | `test_choseong_matching_honors_explicit_initials_whitelist` | integration | PASS |
| 6 | 한 글자·혼합 문자 term에서는 초성을 파생하지 않는다 | `test_choseong_matching_only_derives_multi_syllable_hangul_terms` | unit | PASS |
| 7 | 같은 초성 충돌 결과가 입력 순서와 무관하다 | `test_choseong_matching_resolves_collisions_deterministically` | determinism | PASS |
| 8 | NFC와 NFKC 설정 모두 호환 자모 입력의 원문을 보존한다 | `test_choseong_matching_supports_nfc_configuration` | Unicode | PASS |
| 9 | 10개 정확도 corpus에서 FP/FN이 없다 | `test_choseong_corpus_has_no_false_positives_or_false_negatives` | corpus | PASS |
| 10 | opt-in 초성 index의 retained memory를 측정한다 | `test_retained_memory_includes_opt_in_choseong_index` | benchmark | PASS |

## 성능 기준선

Windows CPython 3.11.9, warmup 10회 후 100회 측정:

| workload | p50 | p95 | cold start | retained Python allocation |
|---|---:|---:|---:|---:|
| `short-choseong` (사전 2개) | 0.0445 ms | 0.0509 ms | 0.2260 ms | 11,256 bytes |
| `short-choseong-normal-hangul` | 0.0172 ms | 0.0312 ms | 0.1668 ms | 11,256 bytes |
| `choseong-dictionary-1000` | 0.0480 ms | 0.0741 ms | 45.0658 ms | 2,621,488 bytes |

## Coverage와 알려진 제한

- 사용자 편집 중인 `badwords.txt`를 건드리지 않기 위해 commit `1c99723`의 깨끗한 detached
  worktree에서 전체 게이트를 실행했다.
  - `uv sync --all-extras --dev`: PASS
  - `uv run ruff format --check .`: 22 files PASS
  - `uv run ruff check .`: PASS
  - `uv run mypy`: 22 source files PASS
  - `uv run pytest`: 232 passed, total coverage 95.91%
  - `uv build`: sdist와 wheel PASS
  - 잠금 의존성 `pip-audit`: 알려진 취약점 없음(Koguard 자체는 PyPI 미등록으로 audit 제외)
- 초성 사이 공백·구분자, 한글 자판 변환, 유사 철자·발음은 지원하지 않는다.
- 작은 수동 corpus의 precision/recall 1.0은 실제 서비스 정확도를 의미하지 않는다.
- 사용자가 로컬에서 편집한 외부 `slang.csv` 기반 목록은 원본 저장소가 해당 파일의 라이선스를
  `확인 필요`로 표시하므로 이 기능 브랜치와 배포 사전에 포함하지 않았다.
