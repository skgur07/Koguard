# Koguard

[![CI](https://github.com/skgur07/Koguard/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/skgur07/Koguard/actions/workflows/ci.yml)

한국어 욕설·비속어 탐지를 위한 경량 Python 라이브러리입니다.

현재 v0.1에서는 기본 사전 기반 Exact Match, 반복·구분자 우회 view, 공백·혼합·초성·명시적
Alias 매칭, 영문 두벌식 자판·호환 자모 조합, 독립 토큰 Fuzzy Match와 구간 단위 Whitelist
처리를 제공합니다. 기본 `balanced` profile은 Exact·Alias·Choseong만 사용하고, 모든 우회
단계가 필요한 경우 `aggressive`를 선택할 수 있습니다.

> **개발 우선순위:** Adapter·Plugin·AI 구현은 현재 보류했습니다. 최초 공개 `0.1.0` 전까지
> 탐지 데이터, 독립 평가 corpus와 단순 사용자 API를 먼저 완성합니다. profile API와
> `balanced` 기본값은 구현했으며, 변경 근거와 남은 품질 게이트는
> [제품 집중 계획](https://github.com/skgur07/Koguard/blob/dev/docs/product-focus-plan.md)에 기록되어 있습니다.

실서비스 corpus는 라이선스가 고정된 2,500건 tuning intake와 기존 자료와 중복 없는 1,000건
review buffer까지 확보했고, 이 중 2,363건을 독립 판정으로 확정했습니다. 아직 전체 gold나
hidden evaluation은 아닙니다. 현재 상태와 완료 전 blocker는
[PF-005 corpus 상태](https://github.com/skgur07/Koguard/blob/dev/docs/corpus-intake-status.md)를 참고하세요.

`0.1.0`은 아직 PyPI에 공개하지 않았습니다. PF-013의 MIT·CI·artifact hardening은 완료했고
비공개 취약점 신고도 활성화했습니다. 남은 공개 gate는 저장소 밖 독립 hidden evaluation과
TestPyPI 설치 검증이며, 실제 `main` 승격과 PyPI 업로드는 유지관리자의 별도 승인을 요구합니다.
현재 판정과 안전한 실행 절차는
[PF-014 릴리즈 준비 보고서](https://github.com/skgur07/Koguard/blob/dev/docs/pf014-release-readiness.md)에 기록합니다.

0.1.0의 폐쇄된 import 목록, 제거한 미래 enum과 Adapter·Plugin·AI·masking 비지원 경계는
[공개 API inventory](https://github.com/skgur07/Koguard/blob/dev/docs/public-api-inventory.md)에 기록되어 있습니다.

## 사용법

```python
from koguard import KoguardEngine

engine = KoguardEngine()  # balanced
print(engine.contains("검사할 문장"))  # bool
```

`contains(text)`는 별도 탐지 경로가 아니라 정확히 `check(text).detected`를 반환하는 편의
메서드입니다. 따라서 profile, 직접 설정, 사용자 사전, Whitelist, 입력 검증과 계산량 제한이
`check()`와 완전히 같습니다. match와 원문 span이 필요하면 `check()`를 한 번 호출해 그 결과를
사용하세요. 두 메서드의 전체 계약은 [boolean API 계약](https://github.com/skgur07/Koguard/blob/dev/docs/contains-api.md)에 기록합니다.

```python
result = engine.check("검사할 문장")  # CheckResult
print(result.detected)
print(result.matches)
```

### 탐지 프로필

```python
strict = KoguardEngine(profile="strict")
balanced = KoguardEngine(profile="balanced")
aggressive = KoguardEngine(profile="aggressive")
```

| profile | 활성 범위 | 용도 |
| --- | --- | --- |
| `strict` | Exact + 승인 Alias | 최소 비용의 등록 표현 탐지 |
| `balanced` | Strict + Choseong | 독립 batch에서 증분 TP가 확인된 기본값 |
| `aggressive` | 현재 구현된 모든 matcher | 반복·구분자·공백·자판·자모·Fuzzy 우회까지 검사 |

독립 tuning 2,363건에서 `balanced`는 strict보다 문장 TP 17건을 더 찾고 문장 FP 증분은 0건을
유지했습니다. 공통 FP로 보였던 2건은 블라인드 재감사에서 모두 정책상 positive로 확정되어
hard-negative 1,825건의 문장 FP는 0건입니다. 다만 occurrence FP는 balanced가 6건 더 많아
전체 증분 gate는 아직 실패합니다. 따라서
`balanced` 기본값은 공개 전 hidden 평가와 함께 재검토 대상이며, 최소 오탐이 우선이면 현재도
`strict`를 선택할 수 있습니다.

모든 profile은 사전에 등록된 표현을 문맥과 무관하게 부분 문자열로 탐지하므로 `시발점`도
`시발` match를 반환합니다. profile과 직접 `EngineConfig`는 동시에 전달할 수 없습니다.
해석된 불변 설정은 `engine.config`에서 확인할 수 있습니다. 전체 계약과 첫 독립 평가 수치는
[profile API 계약](https://github.com/skgur07/Koguard/blob/dev/docs/profile-api-contract.md)과
[공개 profile 보고서](https://github.com/skgur07/Koguard/blob/dev/evaluation/results/pf009-profile-evaluation.report.json)에 기록합니다.

기본 사전 대신 직접 만든 사전을 사용할 수도 있습니다.

```python
from koguard import KoguardDictionary, KoguardEngine

dictionary = KoguardDictionary.from_sources(
    blacklist=["금칙어"],
    whitelist=["금칙어가 포함된 정상 표현"],
    include_defaults=False,
)
engine = KoguardEngine(dictionary=dictionary)
```

### 탐지 단계 설정

직접 `EngineConfig`를 만드는 고급 경로에서는 모든 탐지 플래그 기본값이 `True`이며 정확한
`bool` 값만 허용합니다. 인자 없는 `KoguardEngine()`은 이 all-enabled 설정 대신
`balanced` profile을 사용합니다.

| 설정 | 탐지 단계 | 기본값 |
| --- | --- | --- |
| `exact_matching` | 정규화된 사전어 Exact Match | `True` |
| `repeated_matching` | `시이이발` 같은 반복 모음 축약 view | `True` |
| `separator_matching` | `시*!발` 같은 설정 구분자 제거 view | `True` |
| `whitespace_gap_matching` | `시 발` 같은 공백·탭 간격 매칭 | `True` |
| `mixed_gap_matching` | `시 * 발` 같은 공백·구분자 혼합 매칭 | `True` |
| `choseong_matching` | `ㅅㅂ` 같은 독립 초성 토큰 매칭 | `True` |
| `alias_matching` | `ㅈ같네`, `ㅄ` 같은 명시적 축약 규칙 매칭 | `True` |
| `keyboard_matching` | `tlqkf` 같은 영문 두벌식 자판 입력 조합 | `True` |
| `jamo_composition_matching` | `ㅅㅣㅂㅏㄹ` 같은 호환 자모 입력 조합 | `True` |
| `segmented_input_matching` | `ㅅ * ㅂ`, `ㅅㅣ ㅂㅏㄹ`, `tl * qkf` 같은 제한된 조합 우회 | `True` |
| `fuzzy_matching` | 독립 토큰의 제한된 Levenshtein 오타 탐지 | `True` |

각 단계는 독립적으로 `False`로 끌 수 있습니다. 다음 설정은 Exact Match만 남깁니다.

```python
from koguard import EngineConfig, KoguardEngine

config = EngineConfig(
    exact_matching=True,
    repeated_matching=False,
    separator_matching=False,
    whitespace_gap_matching=False,
    mixed_gap_matching=False,
    choseong_matching=False,
    alias_matching=False,
    keyboard_matching=False,
    jamo_composition_matching=False,
    segmented_input_matching=False,
    fuzzy_matching=False,
)
engine = KoguardEngine(config=config)
```

기본 사전은 프로젝트에서 직접 선별한 표현, MIT Korcen에서 선별한 표현, 독립 검토 뒤
MIT `2runo/Curse-detection-data`에서 승격한 표현을 포함하며 기본 Whitelist는 비어 있습니다.
소문자 로마자 literal `sibal`, `ssibal`, `shibal`도 Exact Match로 탐지합니다. 고정한 원본
revision과 라이선스는
[`src/koguard/data/NOTICE.md`](https://github.com/skgur07/Koguard/blob/dev/src/koguard/data/NOTICE.md)에 기록합니다.
따라서 `시발점`, `병신년`처럼 금칙어를 포함한 복합어도 기본 정책에서는 탐지합니다.
서비스 문맥에서 허용할 표현은 `whitelist` 또는 `whitelist_path`로 명시적으로 주입해야 합니다.

`aggressive`의 반복 문자 view는 앞 음절과 같은 모음의 독립 음절을 두 번 이상 늘인 표현을
추가 탐지합니다. 예를 들어 `시이이발`은 `시발`로 탐지되며 결과의 `matched_text`와 span은
원문 전체를 가리킵니다. 한 번만 추가된 `시이발`은 축약하지 않습니다.

`aggressive`의 특수문자 view는 문자 사이에 삽입된 `!@#$%^&*_-+=~.·,` 기호를 제거해
탐지합니다.
예를 들어 `시*!발`은 `시발`로 탐지되며 원문 span은 삽입된 기호까지 포함합니다. 제거할
문자 집합은 `EngineConfig.obfuscation_separators`로 제한할 수 있고, 공백이나 영숫자는
구분자로 설정할 수 없습니다.

공백 삽입과 공백·구분자 혼합 우회 탐지는 `aggressive` 또는 직접 만든 기본
`EngineConfig()`에서 활성화됩니다. 필요하면 서로 독립적으로 끌 수 있습니다.

```python
from koguard import EngineConfig, KoguardEngine

config = EngineConfig(
    whitespace_gap_matching=False,
    mixed_gap_matching=False,
    max_whitespace_gap=3,
)
engine = KoguardEngine(config=config)
```

해당 설정을 켜면 사전 단어의 글자 사이에 들어간 짧은 공백과 탭을 허용하며, 공백과 설정된
`obfuscation_separators`를 함께 섞은 `시 * 발`도 탐지합니다. 각 공백 구간은
`max_whitespace_gap` 이하이어야 하며 줄바꿈은 허용하지 않습니다. 또한 매치 양끝이 영숫자
토큰 중간이면 후보를 버리므로 `시 발`, `시 * 발`, `개 새끼`는 탐지하지만 `시 발표`,
`시 * 발표`, `개 새끼손가락`은 탐지하지 않습니다.

결과의 `matched_text`, `start`, `end`에는 우회 문자를 포함한 원문 구간이 그대로 보존됩니다.
공백·탭만 사용한 결과의 `method`는 `MatchMethod.WHITESPACE`, 공백과 구분자를 모두 사용한
결과는 `MatchMethod.MIXED`입니다.

Whitespace와 Mixed 매칭에서는 Whitelist의 우회 형태를 별도로 확장하지 않습니다. 예를 들어
Whitelist에 `시발 자동차`가 있어도 입력 `시 발 자동차`와 `시 * 발 자동차`의 욕설 구간은
탐지합니다. Whitelist는 입력에 실제로 겹치는 기존 정규화 view의 구간만 보호합니다.

초성 표현 탐지는 기본 `balanced`와 `aggressive`에서 활성화됩니다. 초성 인덱스의 오탐
가능성이나 추가 메모리 비용을 피하려면 `strict`를 사용하거나
`EngineConfig(choseong_matching=False)`로 끌 수 있습니다.

```python
from koguard import KoguardDictionary, KoguardEngine

dictionary = KoguardDictionary.from_sources(
    blacklist=["시발", "씨밤", "개새끼"],
    include_defaults=False,
)
engine = KoguardEngine(dictionary=dictionary)

assert engine.check("ㅅㅂ").matched_word == "시발"
assert engine.check("ㅆㅂ").matched_word == "씨밤"
assert engine.check("ㄱㅅㄲ").matched_word == "개새끼"
```

초성 index는 두 글자 이상의 완성형 한글 blacklist 항목에서만 파생합니다. 입력에서는
`ㅅㅂ`처럼 연속된 호환 자모 또는 동등한 현대 초성 자모 토큰만 비교하고, `수박` 같은 일반
한글 문장을 초성으로 변환하지 않습니다. 또한 `ㄱㅅㅂ`, `ㅅㅂㄹ`, `3ㅅㅂ`처럼 더 긴 영숫자
토큰의 일부는 버립니다. `segmented_input_matching=True`이면 호환 초성 사이의 제한된 공백과
설정 구분자를 추가 view에서 제거하므로 `ㅅ ㅂ`, `ㅅ*ㅂ`, `ㅅ * ㅂ`도 탐지합니다. 공백을
전역 제거하지 않으므로 `시 발표`, `ㅅ 발표`, `ㅅ ㅂㄹ`은 결합하지 않습니다.

여러 blacklist 항목이 같은 초성으로 충돌하면 길이 내림차순·사전순으로 정렬된 첫 항목을
결과의 canonical `term`으로 사용합니다. 특정 초성을 허용하려면 Whitelist에 `ㅅㅂ`처럼
초성 자체를 명시해야 합니다. 탐지 결과의 `method`는 `MatchMethod.CHOSEONG`입니다.

명시적 Alias 탐지도 기본으로 활성화됩니다. 모든 자모 조합을 추측하거나 공백을 전역
제거하지 않고, 구조화된 규칙에 등록된 표현만 비교합니다.

| 기본 Alias | canonical `term` | 경계 모드 |
| --- | --- | --- |
| `ㅈ같` | `좆같다` | `token_prefix` |
| `ㅈ됐` | `좆되다` | `token_prefix` |
| `ㅄ` | `병신` | `exact_token` |
| `ㅈㄲ` | `좆` | `exact_token` |
| `ㅅㅄㄲ` | `시발새끼` | `exact_token` |

`token_prefix`는 토큰 시작에서 일치하고 뒤에 한글 음절 접미부만 이어질 때 허용하므로
`ㅈ같네`와 `ㅈ됐네`를 탐지하지만 `aㅈ같네`, `ㅈ같1`, `ㅈ같네abc`는 버립니다.
`exact_token`은 Alias 전체가 독립 영숫자 토큰이어야 하므로 `ㅄ`은 탐지하지만 `ㅄ1`,
`ㅈㄲㅋ`, `ㅅㅄㄲ네`는 탐지하지 않습니다. `ㅈ 같은 모양`처럼 규칙 내부에 공백이 들어간
표현도 결합하지 않습니다. 결과의 `method`는 `MatchMethod.ALIAS`입니다.

사용자 Alias는 canonical term을 같은 blacklist에 명시한 뒤 추가할 수 있습니다.

```python
from koguard import AliasMode, AliasRule, KoguardDictionary, KoguardEngine

dictionary = KoguardDictionary.from_sources(
    blacklist=["병신"],
    aliases=[AliasRule("ㅄ", "병신", AliasMode.EXACT_TOKEN)],
    include_defaults=False,
)
engine = KoguardEngine(dictionary=dictionary)
```

TSV 파일은 `alias<TAB>term<TAB>mode` 형식으로 `alias_path`에 전달할 수 있습니다. 입력과
Whitelist는 같은 Unicode form으로 정규화되며, Alias 결과도 원문의 `matched_text`와
`[start, end)` span을 보존합니다. 기본 규칙의 조사 출처와 데이터 포함 경계는
[`src/koguard/data/NOTICE.md`](https://github.com/skgur07/Koguard/blob/dev/src/koguard/data/NOTICE.md)에 기록합니다. 필요하면
`EngineConfig(alias_matching=False)`로 이 단계만 끌 수 있습니다.

제로폭 문자, joiner, bidi control 같은 Unicode format character는 보이지 않는 term 분리자로
인정하지 않습니다. 한글에 붙인 combining mark와 variation selector도 탐지 view에서 무시하고,
NFKC 호환 자모는 완성형 한글로 재조합합니다. 이때 반환하는 `matched_text`와 `[start, end)`는
제거된 내부 code point를 포함한 원문 구간을 그대로 가리키며 Whitelist도 같은 구간을
보호합니다. 세부 정책과 측정 결과는
[`docs/unicode-fp-hardening.md`](https://github.com/skgur07/Koguard/blob/dev/docs/unicode-fp-hardening.md)에 있습니다.

영문 두벌식 자판 입력과 호환 자모 입력은 동일한 현대 한글 조합기를 사용하는 별도 view로
처리합니다. `tlqkf`는 영문 키를 `ㅅㅣㅂㅏㄹ`로 치환한 뒤 `시발`로 조합하고,
`ㅅㅣㅂㅏㄹ`은 치환 없이 바로 `시발`로 조합합니다. 두 view 모두 원문 자체를 바꾸지 않으므로
`normalized_text`는 위 Unicode hardening을 적용한 기본 정규화 view를 유지하며, 매치의
`matched_text`와 span은 각각 원래 `tlqkf` 또는 `ㅅㅣㅂㅏㄹ` 전체를 가리킵니다.

```python
from koguard import EngineConfig, KoguardEngine, MatchMethod

engine = KoguardEngine(profile="aggressive")
assert engine.check("tlqkf").method is MatchMethod.KEYBOARD
assert engine.check("ㅅㅣㅂㅏㄹ").method is MatchMethod.JAMO

disabled = KoguardEngine(
    config=EngineConfig(
        keyboard_matching=False,
        jamo_composition_matching=False,
        segmented_input_matching=False,
    )
)
```

변환 view에서도 Whitelist를 다시 계산하므로 Whitelist에 `시발점`을 넣으면 `tlqkfwja`와
`ㅅㅣㅂㅏㄹㅈㅓㅁ`뿐 아니라 `tl * qkfwja`, `ㅅㅣ * ㅂㅏㄹㅈㅓㅁ`도 보호됩니다.

조합 우회 view는 같은 입력 체계의 문자 양쪽에 있는 공백·탭과 설정된
`obfuscation_separators`만 제거합니다. 각 연속 공백은 `max_whitespace_gap` 이하여야 하고
줄바꿈과 설정되지 않은 구분자는 허용하지 않습니다. `segmented_input_matching=False`로 세
조합 우회를 함께 끌 수 있으며, `choseong_matching`, `keyboard_matching`,
`jamo_composition_matching`을 끄면 해당 입력 체계의 조합 우회도 함께 꺼집니다. 결과 method는
각각 기존 `CHOSEONG`, `KEYBOARD`, `JAMO`를 사용하고 원문 span에는 제거된 구간이 포함됩니다.
세벌식이나 일반 로마자 변환은 지원하지 않습니다. 등록된 소문자 로마자 literal만 Exact
Match하며 대문자·혼합 대소문자나 등록되지 않은 다른 표기를 자동 변환하지 않습니다.

Fuzzy 탐지는 `aggressive` 또는 직접 설정했을 때 사전어와 편집거리 1인 독립 영숫자 토큰을
탐지합니다. 1~2글자 사전어는 오탐 보호를 위해 Exact Match만 사용하고, 기본 threshold에서는
3~32글자 사전어만 Fuzzy index에 포함합니다. 예를 들어 `개세끼`, `개끼`, `개새애끼`는
`개새끼`로 탐지하며 결과의
`method`는 `MatchMethod.LEVENSHTEIN`, `score`는
`1 - distance / max(len(token), len(term))`입니다.

```python
from koguard import EngineConfig, KoguardEngine

config = EngineConfig(
    fuzzy_matching=True,
    fuzzy_min_term_length=3,
    fuzzy_max_term_length=32,
    fuzzy_max_distance=1,
    fuzzy_min_score=0.0,
    fuzzy_max_operations=250_000,
    fuzzy_max_index_entries=100_000,
)
engine = KoguardEngine(config=config)
```

Fuzzy는 모든 Exact·우회 탐지보다 낮은 우선순위로 실행하며 기존 Whitelist와 상위 매치 구간을
침범하지 않습니다. 정상 복합어 오탐을 제한하기 위해 토큰 일부나 조사·어미가 붙은 오타는
결합하지 않습니다. 입력별 연산량이 `fuzzy_max_operations`를 넘으면 부분 결과 대신
`FuzzyOperationLimitError`를 발생시킵니다. 사전 생성 시 삭제 서명 index가
`fuzzy_max_index_entries`를 넘으면 설정 오류로 거부합니다.

## 개발 환경

Python 3.11.9와 [uv](https://docs.astral.sh/uv/)를 사용합니다.

```powershell
uv sync
uv run python -c "import koguard; print(koguard.__version__)"
```

## 개발 명령

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

## 성능 기준선

저장소 루트에서 다음 명령을 실행하면 고정 corpus의 p50·p95 지연 시간, 처리량, cold start,
steady-state peak memory를 JSON으로 기록합니다.

```powershell
uv run python -m benchmarks.engine_benchmark `
  --iterations 100 `
  --warmups 10 `
  --output benchmarks/results/local.json
```

측정 항목과 결과 해석은 [`benchmarks/README.md`](https://github.com/skgur07/Koguard/blob/dev/benchmarks/README.md)를 참고합니다.

## 개발 자동화 하네스

Koguard는 [Everything Claude Code(ECC)](https://github.com/affaan-m/ECC)의 계획, TDD,
검증, 전문 역할 분리 패턴을 프로젝트 로컬 Codex 설정으로 적용합니다.

- 저장소 규칙: [`AGENTS.md`](https://github.com/skgur07/Koguard/blob/dev/AGENTS.md)
- Codex 탐색 지도: [`docs/CODEX-NAVIGATION-GUIDE.md`](https://github.com/skgur07/Koguard/blob/dev/docs/CODEX-NAVIGATION-GUIDE.md)
- 개발 워크플로: [`docs/development-workflow.md`](https://github.com/skgur07/Koguard/blob/dev/docs/development-workflow.md)
- 코드 리뷰 기준: [`docs/code-review.md`](https://github.com/skgur07/Koguard/blob/dev/docs/code-review.md)
- DAILY/LIBRARY 분류: [`docs/ecc-install-plan.md`](https://github.com/skgur07/Koguard/blob/dev/docs/ecc-install-plan.md)

전역 모델, 알림, MCP 서버, 자격 증명 설정은 변경하지 않습니다.

## 라이선스

Koguard 코드와 프로젝트가 직접 선별한 데이터는 [MIT License](https://github.com/skgur07/Koguard/blob/dev/LICENSE)로
배포합니다. 기본 사전에 포함된 외부 선별 literal의 고정 revision과 고지는
[dictionary NOTICE](https://github.com/skgur07/Koguard/blob/dev/src/koguard/data/NOTICE.md)와 각 MIT
라이선스 파일에 보존합니다.
