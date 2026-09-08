# Koguard 프로젝트 검토 피드백

- 검토일: 2026-09-08
- 검토 기준: `ade45f2fd44d9cc468dfdc281c14174622492e14`의 로컬 작업 트리
- 환경: Windows, CPython 3.11.9, uv 0.12.2
- 범위: 공개 API, 탐지 파이프라인, 설정·사전 검증, 관련 테스트, 공개 평가 근거, 패키징·배포 도구
- 산출물: 이 피드백 문서. 런타임 코드·사전·테스트와 기존 출시 판정은 수정하지 않았다.
- 방법: 영역별 읽기 전용 리뷰, 직접 작성한 입력과 mock을 이용한 재현, 전체 로컬 품질 검사

## 1. 확인된 개선 사항

우선순위는 [코드 리뷰 기준](code-review.md)을 따른다. 아래에는 재현한 문제와
현재 출시 상태의 불일치만 포함한다. 알려진 제품 정책과 후속 제안은 뒤에서 별도로 설명한다.

| ID | 우선순위 | 내용 | 영향 범위 |
| --- | --- | --- | --- |
| F-01 | P1 | 반복 축약에서 긴 동일 문자 구간을 제곱 시간으로 재탐색 | `aggressive`, 반복 매칭을 켠 직접 설정 |
| F-02 | P2 | 사전 factory가 문자열 하나를 글자별 항목으로 등록 | 사용자 blacklist·whitelist |
| F-03 | P2 | 긴 Alias가 보호되면 같은 위치의 짧은 유효 Alias도 누락 | 사용자 Alias와 Whitelist 조합 |
| F-04 | P2 | 잘못된 설정의 예외 종류가 입력 내용·타입에 따라 달라짐 | 사전·설정 오류 처리 |
| F-05 | P2 | 고정 출시 후보와 이후 코드 변경의 출시 포함 범위가 불명확 | 출시 현황판·README·TestPyPI 대상 |
| F-06 | P2 | Windows 드라이브 경로가 sdist 경로 안전성 감사를 통과 | 배포물 감사 도구 |
| F-07 | P2 | release report CLI가 문서화된 `GITHUB_TOKEN`을 전달하지 않음 | GitHub CI 근거 조회 |

### F-01. 반복 축약의 최악 입력 비용을 선형으로 제한할 것

**근거:** [normalizer](../src/koguard/engine/normalizer/__init__.py) 829–830, 845–847행.
`build_repeated_view()`는 같은 문자 구간의 끝까지 탐색한 뒤, 축약 대상이 아니면 한 글자만
진행한다. 다음 반복에서 남은 동일 구간을 다시 훑는다. 입력 어딘가에 반복 모음이 있으면
빠른 반환 조건도 통과하므로, 이후의 긴 일반 문자 반복이 O(n²) 비용을 만든다.

```python
from time import perf_counter
from koguard import KoguardDictionary, KoguardEngine

dictionary = KoguardDictionary.from_sources(
    blacklist=["차단어"], include_defaults=False
)
text = "이이" + "가" * 4094
for profile in ("strict", "balanced", "aggressive"):
    engine = KoguardEngine(profile=profile, dictionary=dictionary)
    start = perf_counter()
    result = engine.check(text)
    print(profile, result.detected, (perf_counter() - start) * 1000)
```

허용 최대 길이 4,096자에서 모두 미탐지이며, 로컬 관측 시간은 strict 3.38ms,
balanced 3.59ms, aggressive 802.65/833.86ms였다. 다른 검사와 병행했으므로 이 시간은
공식 benchmark가 아니다. 별도 문자 접근 계측에서는 입력 길이 1,024/2,048/4,096에 따라
접근 횟수가 522,758/2,094,086/8,382,470으로 증가해 제곱 비용을 확인했다.

기본 balanced에는 해당 단계가 꺼져 있지만, aggressive를 사용하는 동기 요청 처리에서는
짧은 요청 하나가 상당한 CPU 시간을 차지한다. Fuzzy 연산 상한은 앞선 정규화 비용을
제한하지 않는다.

**수정 방향·완료 조건:** 동일 구간의 길이를 반복 계산하지 않도록 순회 구조를 바꾼다.
구간 첫 글자 뒤에서 새로 성립하는 모음 축약과 원문 span 의미를 보존해야 한다.
기존 반복 축약 테스트에 위 비축약 구간 사례를 추가하고, 입력 길이에 따른 연산 증가와
4,096자 실제 엔진 지연을 확인한다. 환경에 민감한 절대 시간 assertion만으로 회귀를 막지 않는다.

### F-02. `from_sources()`의 collection 자체를 먼저 검증할 것

**근거:** [dictionary.py](../src/koguard/engine/dictionary.py) 208–209행.
직접 생성자는 131–132행에서 단일 문자열 collection을 거부하지만 권장 factory는 먼저 순회한다.

```python
from koguard import KoguardDictionary, KoguardEngine

dictionary = KoguardDictionary.from_sources(
    blacklist=["bad"], whitelist="badge", include_defaults=False
)
print(dictionary.ordered_whitelist)  # ('a', 'b', 'd', 'e', 'g')
print(KoguardEngine(profile="strict", dictionary=dictionary).contains("bad"))
# False: 한 글자 Whitelist와 겹쳐 blacklist 표현이 보호됨
```

반대로 `blacklist="bad"`는 `a`, `b`, `d`를 각각 금칙어로 등록해 탐지 범위를 넓힌다.
리스트 괄호를 빠뜨리는 설정 실수가 조용히 탐지 정책을 바꾸는 문제다.

**수정 방향·완료 조건:** factory 진입 시 `str`·`bytes`와 비 iterable 입력을 검증하고
직접 생성자와 동일한 `DictionaryError` 계약을 적용한다. 정상 list·tuple·generator는
유지하고 단일 문자열, bytes, 잘못된 collection 타입의 회귀를 추가한다.

### F-03. 보호된 긴 Alias 뒤에 짧은 후보를 다시 평가할 것

**근거:** [matcher.py](../src/koguard/engine/matcher.py) 1157–1166행.
시작 위치별 최장 Alias가 Whitelist와 겹치면 폐기하고, 같은 위치의 짧은 후보를 재검토하지 않는다.

```python
from koguard import AliasMode, AliasRule, KoguardDictionary, KoguardEngine

dictionary = KoguardDictionary.from_sources(
    blacklist=["차단어"], whitelist=["허용"], include_defaults=False,
    aliases=[
        AliasRule("금칙", "차단어", AliasMode.EXACT_TOKEN),
        AliasRule("금칙 허용", "차단어", AliasMode.EXACT_TOKEN),
    ],
)
print(KoguardEngine(profile="strict", dictionary=dictionary).check("금칙 허용").matches)
# ()
```

긴 Alias를 제거하면 `금칙`의 `[0, 2)` 구간이 탐지된다. 이 구간은 허용 표현의 `[3, 5)`와
겹치지 않는다. Alias를 추가하는 것만으로 기존 비보호 탐지가 사라져 구간별 보호 원칙과 충돌한다.

**수정 방향·완료 조건:** 긴 후보가 보호·선택 구간과 겹칠 때 짧은 후보의 경계 조건을
재평가한다. 같은 시작점의 긴/짧은 Alias, 뒤쪽 Whitelist, 다중 매치와 원문 위치를 함께 검증한다.
기존 [Alias 테스트](../tests/test_alias_matching.py) 133행의 서로 다른 위치 사례만으로는
이 조합을 포착하지 못한다.

### F-04. 정규화 전에 설정을 검증해 공개 예외 계약을 맞출 것

**근거:** [dictionary.py](../src/koguard/engine/dictionary.py) 208, 241–245행과
[config.py](../src/koguard/config.py) 45, 73–75행.
공개 예외의 의도는 [API inventory](public-api-inventory.md) 23–24, 55–58행에 설명되어 있다.

| 재현 조건 | 실제 결과 | 맞춰야 할 계약 |
| --- | --- | --- |
| `from_sources(blacklist=["Ａ"], unicode_form="INVALID", include_defaults=False)` | `ValueError` | `DictionaryError` |
| 같은 설정에서 `blacklist=["bad"]` | `DictionaryError` | 내용과 관계없이 동일 예외 |
| `EngineConfig(unicode_form=[])` | `TypeError: unhashable type` | `ConfigurationError` |
| `EngineConfig(obfuscation_separators=frozenset({1}))` | 정규화 함수의 `TypeError` | `ConfigurationError` |

이는 잘못된 입력을 허용하는 문제보다, 전용 예외를 처리하는 호출자의 실패 경로를 벗어나는
문제다. 사전 factory가 Unicode form을 검증하기 전에 정규화를 시작하고, 설정 객체도
항목 타입 확인 전에 set 조회나 Unicode 함수를 실행한다.

**수정 방향·완료 조건:** 사전 읽기·정규화 이전에 form과 collection·구분자 항목 타입을
검증한다. ASCII, 호환 문자, 빈 사전과 비문자열 설정이 각각 동일한 전용 예외로 실패하는지
공개 API 테스트로 확인한다.

### F-05. 출시 후보와 현재 HEAD의 포함 범위를 현황판에 명시할 것

**근거:** [PF-014 보고서](pf014-release-readiness.md) 102–104, 115행,
[TestPyPI workflow](../.github/workflows/publish-testpypi.yml) 31, 44행,
[출시 실행 현황판](release-0.1.0-execution-plan.md).

고정 RC는 `813fc36c6988a7bdab68027964a206e970ab9f52`다. 이후 HEAD에는
`110faa3`의 matcher·normalizer 최적화와 `ade45f2`의 Whitelist 변경이 들어갔다.
`git diff --stat 813fc36 HEAD -- src/koguard`로 3개 파일의 차이를 확인했다.
현재 README는 새 Whitelist 동작을 설명하지만 TestPyPI workflow는 이전 RC의 산출물만 내려받는다.

9월 4일 문서와 hidden·CI 기록은 해당 RC의 역사적 근거로 유효하다. 그러나 현재 HEAD의
기능·정확도·성능을 검증한 증거로 사용할 수 없고, 기존 RC를 게시하면 최신 수정은 포함되지 않는다.
release report가 commit·wheel hash를 검사하므로 검증되지 않은 HEAD가 자동 승인된다는 뜻은 아니다.

**수정 방향·완료 조건:** 기존 RC를 출시할지 최신 수정을 담은 새 RC를 만들지 결정한 내용을
실행 현황판에 기록한다. 전자라면 최신 수정의 제외 범위와 해당 artifact용 설명을 명시한다.
후자라면 새 commit·artifact에 대한 품질·평가·설치 근거를 마련하고, hidden 처리는 기존
[split 정책](corpus-split-policy.md)에 따른다. 이전 평가 결과를 덮어쓰거나 새 후보의 결과로 바꾸지 않는다.

### F-06. archive 경로 검사에 Windows 경로 의미를 포함할 것

**근거:** [artifact_audit.py](../release/artifact_audit.py) 180–183, 235–240행.
`PurePosixPath("C:/LICENSE").is_absolute()`는 `False`이고, sdist는 루트 종류가 하나인지도
검사하지만 그 이름을 제한하지 않는다.

기존 합성 sdist fixture의 루트를 `koguard-0.1.0/`에서 `C:/`로 바꾼 메모리 TAR가 필수 파일
26개를 포함한 상태로 감사를 통과했다. Windows 경로 결합에서는
`ntpath.join("D:\\install", "C:/LICENSE") == "C:/LICENSE"`여서 추출 목적지 밖을 가리킨다.

이 결과는 **배포물 감사의 경로 탈출 검사 누락**이다. 실제 uv 설치기의 취약점이나 현재
빌드한 배포물의 오염을 확인한 것은 아니다. 실제 경로 탈출 추출도 실행하지 않았다.

**수정 방향·완료 조건:** Windows drive·UNC·역슬래시 등 경로 형태를 OS와 무관하게
거부하고 sdist 최상위 디렉터리가 기대한 package/version인지 확인한다. drive 절대·상대 경로와
기존 POSIX 절대 경로·`..`·중복 파일을 합성 archive로 회귀 검증한다.

### F-07. release report CLI의 인증 토큰 전달을 연결할 것

**근거:** [release_report.py](../release/release_report.py) 904–907행,
[github_actions_evidence.py](../release/github_actions_evidence.py) 150, 159–160, 184행,
[문서의 토큰 안내](pf014-release-readiness.md) 75–78행.

release report CLI는 `fetch_github_actions_evidence()`에 `token`을 전달하지 않는다.
하위 함수의 기본값은 `None`이며 환경변수를 직접 읽지 않는다. 독립 evidence CLI는 환경변수를
전달하므로 두 진입점의 동작이 다르다. 합성 환경변수와 fetch mock을 사용한 CLI 재현에서도
토큰 keyword 전달이 없음을 확인했다. 실제 자격 증명이나 네트워크는 사용하지 않았다.

**수정 방향·완료 조건:** 문서대로 `GITHUB_TOKEN`을 명시적으로 전달하고, 토큰 설정/미설정
CLI 회귀를 추가한다. 비인증 rate limit이나 인증이 필요한 조회에서 환경변수를 설정해도 실패하는
문제를 해소하되, 토큰을 출력·직렬화하지 않는 계약을 유지한다.

## 2. 유지할 강점과 제품 판단

- core는 외부 런타임 의존성 없이 동작하며 설정·결과 모델은 불변이다. `contains()`가
  `check().detected`를 그대로 사용해 공개 경로의 정책 차이를 줄인다.
- 원문 span, 매치 순서, Unicode, 구간별 Whitelist를 공개 동작으로 검증하는 테스트가 있다.
  이번 790개 테스트도 모두 통과했다. 위 finding은 기존 테스트 밖의 조합·최악 입력을 보완할 과제다.
- 현재 `KoguardEngine()`의 balanced는 Exact·Alias·Choseong이고, 직접 만든 `EngineConfig()`는
  모든 matcher 활성화다. 이 차이는 현재 코드와 profile 문서에 일관되게 명시되어 있다.
- 평가 원문과 공개 집계를 분리하고, 사전 출처 검증·배포물 내용 감사·새 환경 설치·CI 후보
  바이트 재현성 검사를 갖췄다. 이 기반을 유지하면서 F-05~07의 경계를 보완하는 편이 좋다.

다음 항목은 새 코드 결함으로 세지 않았다.

| 항목 | 판단과 후속 제안 |
| --- | --- |
| 정상 문장 오탐 | `고양이가 새끼를 낳았다` 같은 문장은 현재 테스트에서도 탐지를 의도적으로 고정한다. 문맥 무관 정책과 서비스 기대의 차이이므로 제품 정책 변경으로 다뤄야 한다. |
| 평가 표본 | 공개 hidden 집계는 424건 중 positive 16건이다. tuning 문장 FP 0도 다른 분포의 무오탐을 보장하지 않는다. 최신 Whitelist 변경은 이전 집계와 분리해 설명해야 한다. |
| 한 단계만 끄는 README 예시 | `EngineConfig(choseong_matching=False)`는 기본 balanced에서 초성만 끄는 것과 다르다. `dataclasses.replace(engine.config, choseong_matching=False)` 예시를 추가하면 의도치 않은 탐지 확대를 줄일 수 있다. |
| CI 산출물 보존 | authoritative artifact는 14일 보존인데 TestPyPI는 특정 run을 고정한다. 승인 지연 시 동일 바이트를 보존·복원하는 절차가 필요하다. 현재 원격 artifact의 만료 여부는 확인하지 않았다. |

Adapter·Plugin·AI 보류는 현재 공개 범위와 맞는다. 이번 검토에서 새 프레임워크나 모델 도입을
제안하지 않는다. 우선 최악 입력 비용, 사용자 설정의 실수 방지, 출시 후보의 범위를 정리하는 것이
현재 제품을 사용하는 사람에게 직접적인 이익이 있다.

## 3. 실제 실행한 검증

아래 결과는 피드백 문서를 추가하기 전의 위 기준 HEAD에서 실행했다. 아래 전체 품질 검사에서는
전역 캐시 접근 제한을 피하려고 `UV_CACHE_DIR`을 저장소의 `.uv-cache`로 지정했다.
별도 core 재현은 `.tmp/uv-cache`를 사용했으며 전역 환경 설정은 변경하지 않았다.

| 검사 | 명령 | 결과 |
| --- | --- | --- |
| 환경 동기화 | `uv sync --frozen --offline --all-extras --dev` | 16개 패키지 확인 |
| 포맷 | `uv run --no-sync ruff format --check .` | 80개 파일 통과 |
| 린트 | `uv run --no-sync ruff check .` | 통과 |
| 타입 | `uv run --no-sync mypy` | 80개 파일 통과 |
| 테스트 | `uv run --no-sync pytest -q` | 790 passed, 34.41초 |
| 커버리지 | 위 pytest의 `branch=true` coverage | 총 95.67%, 90% gate 통과 |
| 사전 출처 | `uv run --no-sync python -m evaluation.dictionary_provenance` | 후보 73개·출처 3개, literal 67개·Alias 5개, pending 0 |
| 빌드 | `uv build --out-dir dist/project-review-2026-09-08` | wheel·sdist 생성 성공 |
| wheel 정규화 | `uv run --no-sync python -m release.normalize_wheel --dist-dir dist/project-review-2026-09-08` | 통과 |
| 배포물 감사 | `uv run --no-sync python -m release.artifact_audit --dist-dir dist/project-review-2026-09-08 --output dist/project-review-2026-09-08/artifact-audit.json` | 통과 |
| 새 환경 설치 | `uv run --no-sync python -m release.clean_install_smoke --dist-dir dist/project-review-2026-09-08` | wheel·sdist 각각 설치·quickstart 통과 |

커버리지의 95.67%는 branch 측정이 활성화된 coverage.py의 총 coverage 값이며, 별도로 계산한
순수 분기 비율은 아니다. core만 coverage 대상이므로 평가·배포 도구의 coverage를 나타내지도 않는다.

최초 offline 빌드는 캐시에 `hatchling==1.31.0`이 없어 실패했고, 다음 일반 빌드는 네트워크
제한으로 실패했다. 허용된 재실행에서 고정 빌드 의존성을 내려받아 성공했다. 캐시가 소스 폴더
안에 있다는 uv 경고는 있었으나 후속 artifact audit는 통과했다.

검토용 산출물은 Git ignore 대상인 `dist/project-review-2026-09-08`에 있다.
공식 출시 후보를 교체하거나 게시한 결과가 아니다. 감사 시 기록한 해시는 다음과 같다.

- wheel: `214b9c4b449d0f5cd755924e32baed73c537d4f6cbbb1699e645b952119815d1`
- sdist: `1619af30f41088cab3313ef7ee99e3f37a0c84d76164fe5cb54429d5bd6f9629`

## 4. 권장 처리 순서와 미검증 범위

1. **F-01을 먼저 재현 테스트로 고정하고 수정한다.** 기본값 밖의 aggressive도 공개된 기능이므로
   최대 허용 입력에 대한 계산량을 관리해야 한다.
2. **F-02~04의 입력·겹침 계약을 보완한다.** 정상 데이터 변경보다 경계 검증을 먼저 일관되게 만든다.
3. **F-05의 출시 범위를 확정하고 F-06~07을 보완한다.** 기존 RC 유지 또는 새 RC 선택을 명확히
   기록한 뒤 해당 후보의 배포 검증을 수행한다.
4. **해당 후보로 전체 품질 검사와 공개 gate를 완료한다.** TestPyPI 동일 artifact 설치 증거와
   유지관리자 공개 승인은 기존 실행 현황판에 남아 있는 단계이며 이번 검토에서는 수행하지 않았다.

이번 검토에서는 보호된 hidden/private/tuning intake·annotation·quarantine 원문을 열지 않았고,
실서비스 데이터 정확도를 다시 측정하지 않았다. 공개 aggregate는 과거 후보의 근거로만 검토했다.
원격 CI 최신 상태, TestPyPI, PyPI, GitHub artifact의 현재 가용성도 조회하거나 변경하지 않았다.
Windows 이외 플랫폼, 전체 adversarial benchmark, 모든 조합의 완전한 보안 감사는 수행하지 않았다.

새 테스트를 저장하지 않은 이유는 요청이 수정 구현이 아닌 피드백 정리이기 때문이다.
재현 입력·관측 결과·권고 회귀 범위를 이 문서에 남겼으며 구현 작업에서는 먼저 실패 테스트로 옮긴다.

## 5. 보고서 자체 점검

`agent-self-evaluation` 기준으로 정확성·완전성·명확성·실행 가능성·간결성을 각각
4/4/4/4/4점, 평균 4.0/5로 점검했다. 근거와 한계는 다음과 같다.

- 정확성: 실행 결과와 재현을 제시했다. 시간 측정은 병행 실행의 영향을 받아 참고값으로 한정했다.
- 완전성: core·API·배포를 검토했다. 원격 상태와 보호 평가 원문은 범위 밖으로 명시했다.
- 명확성: 결함·알려진 정책·검증을 구분했다. 배포 항목은 commit과 artifact 개념의 이해가 필요하다.
- 실행 가능성: 항목마다 수정 방향과 회귀 조건이 있다. 실제 수정 및 후보 선택은 후속 작업이다.
- 간결성: 첫 표에서 우선순위를 볼 수 있다. 재현과 검사 명령을 보존해 본문은 길어졌다.

가장 유용한 후속 개선은 F-01~04의 재현을 자동화 테스트로 옮기는 일과 F-05의 출시 범위를
실행 현황판에 반영하는 일이다. 사용자는 첫 표로 우선순위를 정하고 각 항목의 근거로 수정 작업을
시작할 수 있다는 점에서 이 평가가 적절하다고 판단한다.
