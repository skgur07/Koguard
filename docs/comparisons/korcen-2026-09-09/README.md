# 수정 후 Koguard와 Korcen 비교

검토일: 2026-09-09. Koguard 기준 commit은
`e6576925cfce46ed0c23356d4610be3a5b0cebbe`이며, 9월 8일 피드백의 core·배포 도구 수정 이후다.
Korcen은 저장소의 기존 비교 계약과 같은 공식 **1.0.3 wheel**을 사용했다.

## 결론

이번에 선택한 입력에서는 **Koguard aggressive가 우회 표현을 더 많이 탐지했고,
기본 balanced는 정상 입력 처리 비용이 낮았다. Korcen은 일부 욕설 입력에서 더 빨랐다.**
반면 기본 balanced는 공백·두벌식·자모·Fuzzy 단계를 사용하지 않으므로 우회 탐지가 aggressive보다
적다. aggressive 결과를 Koguard 기본값의 성능으로 설명하면 안 된다.

전체 제품의 정확도 우열은 아직 결론 낼 수 없다. 사용 가능한 공개 회귀는 Koguard 정책에
맞춰 작성됐고, 추가 진단은 이번 검토자가 직접 선택했다. 특히 정상 진단 20건 중 16건은
이미 Koguard Whitelist 회귀에 포함된 사례이므로 Koguard에 유리한 선택 편향이 있다.

## 1. 비교 대상과 자료

| 항목 | 설정 |
| --- | --- |
| Koguard strict | `KoguardEngine(profile="strict").contains(text)` |
| Koguard balanced | `KoguardEngine().contains(text)`와 같은 기본 설정 |
| Koguard aggressive | 모든 matcher를 사용하는 공개 profile |
| Korcen | `korcen.check(text, foreign=False)`, 사용자 포함·제외 파일 없음, `id=None` |
| 공통 환경 | Windows, CPython 3.11.9, 같은 별도 가상 환경에 공식 wheel 설치 |
| 의존성 | Korcen 비교 환경에 `better-profanity==0.7.0`, `colorama==0.4.6`; Koguard 런타임 의존성 없음 |

Korcen의 공식 API와 배포물은 [PyPI 1.0.3 페이지](https://pypi.org/project/korcen/1.0.3/)와
[공식 저장소](https://github.com/Tanat05/korcen)를 확인했다. 실제 측정은 GitHub 최신 코드가 아닌
아래 hash의 wheel로 고정했다. PyPI의 설명상 선택 의존성 안내와 별개로 이 wheel의 METADATA에는
`better_profanity`, `colorama`가 `Requires-Dist`로 선언되어 있다.

| 배포물 | SHA-256 |
| --- | --- |
| Koguard 0.1.0 | `f5e5e13ed31b6cf88e586476b0259391723c4566e57d2b48dbb91f181d17f3ec` |
| Korcen 1.0.3 | `5139fb973ab40f2f4caaa722c97553397993e6a83a463a1098a85061834fb446` |

자료는 서로 합산해 하나의 정확도로 만들지 않았다. 일부 입력이 자료 간에 중복되므로
아래 건수를 모두 합쳐 독립 표본 수로 해석해서도 안 된다.

| 자료 | 건수 | 용도 |
| --- | ---: | --- |
| 기존 공개 `provisional-ablation.json` | 20: positive 16, negative 4 | 기존 lexical 정책 기준의 회귀 비교 |
| 직접 표현 진단 | 12 | 명시적 표현의 탐지 여부 |
| 우회 표현 진단 | 12 | 반복·공백·초성·자판·자모·오타·대문자 로마자 사례 |
| 정상 문장 진단 | 20 | 일반 문장과 기존 Whitelist 사례의 탐지 여부 |
| 정책 경계 진단 | 8 | 복합어·다의어·URL 등; 정오 판정 없이 출력만 비교 |

추가 52건은 실행 전에 [diagnostic-cases.json](diagnostic-cases.json)에 고정했다.
이는 독립 gold나 새 공식 tuning corpus가 아니다. 실행 결과를 보고 label이나 표본을 바꾸지 않았다.

### 2,763건 자료를 다시 찾은 결과

저장소에는 [최종 tuning profile 보고서](../../../evaluation/results/pf014-r3-final-tuning.profile.report.json)가
있다. 이 파일의 `source.corpus`에는 2,763건, positive 639, negative 2,124와 해시가 있지만,
개별 원문·정답은 없다. Git 추적 파일과 로컬의 ignored 파일 경로도 확인했으나, 문서가 가리키는
확정 `evaluation/annotation-work` 자료는 현재 체크아웃에서 찾지 못했다.

현재 `evaluation/corpus/tuning`의 직접 작성 자료는 100+250+480=830건이며 모두 `review`다.
집계 수치에서 원문을 복원하거나 review를 임의 확정하여 Korcen 정확도를 계산하지 않았다.
확정 원문이 별도로 확보되면 두 제품을 그 자료에 다시 실행해야 한다. 기존 Koguard 집계와
이번 Korcen의 다른 표본 수치를 나란히 놓고 우열을 계산할 수 없다. Hidden 원문은 사용하지 않았다.

## 2. 탐지 비교

숫자는 해당 묶음에서의 탐지 건수다. 정상 문장 행은 **오탐 건수이므로 작을수록 좋다.**

| 진단 묶음 | strict | balanced 기본값 | aggressive | Korcen 1.0.3 |
| --- | ---: | ---: | ---: | ---: |
| 직접 표현 12건 탐지 | 10 | 10 | 10 | 9 |
| 우회 표현 12건 탐지 | 2 | 3 | 11 | 7 |
| 정상 문장 20건 오탐 | 0 | 0 | 0 | 5 |

이번 직접 표현에서 두 제품 모두 `멍청이`, `븅신`을 탐지하지 않았다. Korcen은 `씨발`도
탐지하지 않았으며, 별도 단독 호출에서 `씨발`, `씨발!`, `씨발 진짜`가 모두 False인 것을
재확인했다. 이는 고정 1.0.3 wheel의 관측 결과이며 다른 버전에 일반화하지 않는다.

### 차이가 드러나는 입력

| 입력 | balanced | aggressive | Korcen |
| --- | --- | --- | --- |
| `시이이발` | 미탐지 | 탐지 | 미탐지 |
| `시*!발` | 미탐지 | 탐지 | 미탐지 |
| `시 발` | 미탐지 | 탐지 | 탐지 |
| `시 * 발` | 미탐지 | 탐지 | 미탐지 |
| `ㅅㅂ` | 탐지 | 탐지 | 탐지 |
| `tlqkf` | 미탐지 | 탐지 | 탐지 |
| `ㅅㅣㅂㅏㄹ` | 미탐지 | 탐지 | 미탐지 |
| `ㅅ * ㅂ` | 미탐지 | 탐지 | 미탐지 |
| `개세끼` | 미탐지 | 탐지 | 탐지 |
| `SIBAL` | 미탐지 | 미탐지 | 탐지 |
| `위기가 닥쳐올 것이다` | 미탐지 | 미탐지 | 탐지 |
| `서랍을 뒤져 보았다` | 미탐지 | 미탐지 | 탐지 |

Korcen에서 탐지된 정상 진단 5건은 `닥쳐올`, `닥쳐온`, `닥쳐서`, `뒤져 보았다`, `뒤져도`가
포함된 문장이다. Koguard의 새 기본 Whitelist가 이번 묶음에서는 효과가 있었다.
하지만 아래의 열린 문맥 사례는 Koguard도 여전히 탐지한다.

| 정책 경계 입력 | balanced | aggressive | Korcen |
| --- | --- | --- | --- |
| `시발점은 시작 위치다` | 탐지 | 탐지 | 미탐지 |
| `역사 기록의 병신년` | 탐지 | 탐지 | 탐지 |
| `새끼손가락을 다쳤다` | 탐지 | 탐지 | 미탐지 |
| `촛불이 바람에 꺼져 어두워졌다` | 탐지 | 탐지 | 탐지 |
| `온 집을 뒤질 각오로 찾았다` | 탐지 | 탐지 | 탐지 |
| `고양이가 새끼를 낳았다` | 탐지 | 탐지 | 탐지 |
| `시 발표` | 미탐지 | 미탐지 | 미탐지 |
| `https://example.com/시발` | 탐지 | 탐지 | 미탐지 |

복합어와 URL 내부 표현까지 찾는 것이 필요한 서비스에서는 Koguard의 정책이 맞을 수 있고,
정상 복합어를 허용하는 서비스에서는 별도 Whitelist가 필요하다. 이 표의 모든 탐지를
일괄 오탐 또는 정탐으로 세지 않았다. Korcen도 규칙 기반이며 위 결과가 일반적인 문맥 이해를
증명하지는 않는다.

### 기존 공개 회귀 20건

| 대상 | TP | FP | FN | TN | 문장 recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| strict | 4 | 0 | 12 | 4 | 25.00% |
| balanced | 5 | 0 | 11 | 4 | 31.25% |
| aggressive | 13 | 0 | 3 | 4 | 81.25% |
| Korcen | 7 | 0 | 9 | 4 | 43.75% |

이 corpus는 정상 문맥의 substring과 특정 우회를 positive로 정의한 **Koguard 정책 회귀**다.
일반적인 욕설 판정 정답이나 독립 경쟁 평가로 간주하지 않는다. 기존 비교 러너는
`current-all-enabled`만 지원하므로 aggressive와 Korcen을 먼저 실행하고, 별도 측정 스크립트의
두 대상 문장 TP/FP/FN/TN이 기존 러너와 일치하는지도 확인했다.
원본 출력은 [official-runner.json](official-runner.json)에 보존했다.

## 3. 성능 비교

대상마다 새 Python 프로세스를 사용했다. 같은 프로세스 안에서 엔진을 재사용하고 각 입력에
10회 warmup 후 100회 측정했다. 대상 순서를 회전한 3라운드를 순차 실행했으며 아래 값은
**라운드별 p95의 중앙값**, 단위는 ms다. import·초기화·프로세스 시작 시간은 포함하지 않는다.
아래 다섯 입력에서는 네 대상의 탐지 여부가 각각 동일함을 확인했다.

| 입력 | strict | balanced | aggressive | Korcen |
| --- | ---: | ---: | ---: | ---: |
| 짧은 정상 채팅 | 0.0222 | 0.0262 | 0.0955 | 0.0435 |
| 짧은 욕설 문장 | 0.0306 | 0.0437 | 0.0917 | 0.0068 |
| 정상 패턴 1,024자 | 1.0610 | 1.1692 | 1.7344 | 1.3114 |
| 정상 패턴 4,096자 | 4.3106 | 4.5166 | 7.0015 | 5.2763 |
| 마지막에 욕설이 있는 4,096자 | 4.3841 | 4.3971 | 10.3717 | 1.7762 |

짧은 정상 문장에서는 balanced가 Korcen보다 빨랐지만, 욕설이 발견되는 두 입력에서는
Korcen이 더 빨랐다. Korcen의 `check()`는 카테고리 검사에서 첫 탐지 시 반환하고,
Koguard의 `contains()`는 전체 `check()` 결과를 만든다. 이 호출 구조 차이가 비용에 영향을
줄 수 있다. 측정만으로 시간 차이의 원인을 전부 특정한 것은 아니다.

이전 F-01 재현 형태인 `"이이" + "가" * 4094`의 결과는 다음과 같다.

| strict | balanced | aggressive | Korcen |
| ---: | ---: | ---: | ---: |
| 4.5369ms | 4.4359ms | 7.1093ms | 6.0087ms |

모두 미탐지이며 이번에는 aggressive도 수 ms 범위였다. 과거 검토는 사용자 사전과 병행 실행
조건이 달랐으므로 이전 약 0.8초와의 정확한 속도 향상 배수를 계산하지 않는다.
이번 값은 기본 사전의 독립된 현 상태 관측이다.

`시 * 발`은 aggressive만 탐지하여 수행한 일이 다르므로 동일 기능의 속도 비교에서 제외했다.
전체 7개 workload의 p50·p95와 세 라운드 값은 [results.json](results.json)에 있다.
메모리, cold start, 다른 OS, 실제 서비스 부하의 처리량은 측정하지 않았다.

## 4. 기능과 선택 기준

| 기준 | Koguard | Korcen 1.0.3 |
| --- | --- | --- |
| 기본 확인 API | `contains()`와 상세 `check()` | bool `check()` |
| 상세 결과 | 다중 match, 원문 `[start, end)`, 탐지 방식 | 별도 pattern helper·강조 기능; 비교 API는 bool |
| 설정 | 엔진별 사전·Whitelist·profile | 카테고리 함수, 사용자 필터 파일과 모듈 설정 |
| 강조·마스킹 | 현재 공개 범위 밖 | 강조·마스킹 기능 제공 |
| 다국어 | 한국어 중심 | foreign 옵션; 이번에는 False |
| Python metadata | `>=3.11,<3.12` | `>=3.7` |

Korcen의 기능 설명은 [공식 API 문서](https://pypi.org/project/korcen/1.0.3/) 및 고정 wheel의
함수·metadata 기준이다. `highlight_profanity()`나 `check_and_report_profanity_pattern()`의
존재를 원문 span·canonical term의 완전한 동등성으로 간주하지 않았다.

현재 Koguard는 **원문 위치와 서비스별 정책 제어**가 분명한 차별점이다. 우회 탐지가 필요하면
aggressive 또는 필요한 단계의 직접 설정을 검토할 수 있지만, 기본 balanced의 탐지 범위를
먼저 이해해야 한다. Korcen의 내장 분류·강조 기능과 욕설 입력에서의 빠른 반환도 비교할 가치가 있다.
기능별 수요와 동일한 서비스 표본으로 결정하는 것이 적절하다.

## 5. 재현과 검증

비교용 파일은 `dist/korcen-comparison-2026-09-09` 아래에 두었고 프로젝트 의존성과
런타임 코드는 변경하지 않았다. Korcen wheel과 두 의존성은 PyPI URL·SHA-256을 기록하고
검증한 뒤 별도 환경에 설치했다. 네트워크는 준비 단계에만 사용했다.

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv build --offline --out-dir dist/korcen-comparison-2026-09-09
uv venv --python .venv/Scripts/python.exe dist/korcen-comparison-2026-09-09/venv
```

`results.json`의 `artifacts`에 고정된 세 dependency wheel을 공식 URL에서 내려받아 hash를
검증한 후 `dependencies` 폴더에 두고 `download-manifest.json`에 해당 세 항목을 기록한다.
별도 환경에는 그 wheel들과 방금 빌드한 Koguard wheel을 설치한다.

```powershell
$wheels = @((Get-ChildItem dist/korcen-comparison-2026-09-09/dependencies/*.whl).FullName)
$wheels += (Resolve-Path dist/korcen-comparison-2026-09-09/koguard-0.1.0-py3-none-any.whl).Path
uv pip install --offline --no-index --python dist/korcen-comparison-2026-09-09/venv/Scripts/python.exe $wheels

& dist/korcen-comparison-2026-09-09/venv/Scripts/python.exe -I -X utf8 `
  docs/comparisons/korcen-2026-09-09/run.py `
  --env-python dist/korcen-comparison-2026-09-09/venv/Scripts/python.exe `
  --artifacts dist/korcen-comparison-2026-09-09 `
  --iterations 100 --rounds 3 `
  --output dist/korcen-comparison-2026-09-09/rerun-results.json
```

재측정은 위처럼 다른 출력 파일을 사용해 이 문서의 원본 결과를 보존한다.
`run.py`는 표준 라이브러리만 사용하는 이번 비교 전용 스크립트다. 시간은 `contains()`와
`korcen.check()`를 재고, 모든 라운드에서 판정과 workload 결과가 유지되는지 assertion으로 확인한다.

검증 결과:

- `uv sync --frozen --offline --all-extras --dev`: 통과, 16개 패키지 확인.
- `ruff format --check .`: 81개 파일 통과. `ruff check .`: 통과.
- `mypy`: 기존 검사 대상 80개 파일 통과. 비교 스크립트는 mypy 설정 범위 밖이다.
- `pytest -q`: **839 passed**, branch 측정 활성화 상태의 총 coverage **95.88%**.
- 현재 HEAD의 wheel·sdist build와 별도 환경의 wheel 설치: 통과.
- 기존 비교 러너와 별도 스크립트의 aggressive·Korcen 문장 지표 대조: 일치.
- 3개 라운드의 모든 예측 동일성·workload 탐지 결과 일관성: 통과.

새 제품 동작을 추가하지 않았으므로 별도 기능 테스트는 추가하지 않았다. script의 집계는
기존 러너와의 교차 확인 및 원시 예측으로 검증했다. 이번 결과는 새 RC의 hidden 평가,
TestPyPI smoke, 3 OS CI 또는 공개 승인을 대체하지 않는다.
