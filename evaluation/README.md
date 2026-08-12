# Koguard 평가 러너

이 디렉터리의 비교 러너는 PF-001 corpus의 동일한 gold annotation을 Koguard와
Korcen에 각각 입력하고, 문장 단위 및 가능한 범위의 occurrence 단위 지표를 JSON으로
기록한다. 평가 대상 패키지는 코어 런타임 의존성에 추가하지 않으며, 네트워크 접근도
러너 밖에서만 수행한다.

## PF-004 split guard

`split_guard.py`는 stable case ID manifest와 실제 corpus의 `corpus_id`·split이 일치하는지
검사한다. 공개 regression/tuning과 hidden evaluation 사이의 동일 원문, NFKC·casefold·
구두점/공백/format 제거·연속 반복 축약 후 중복을 차단한다. hidden evaluation과 private
원문이 repository root 아래 있으면 검증에 실패하며 오류와 성공 출력에는 원문을 남기지 않는다.

```powershell
uv run python -m evaluation.split_guard `
  evaluation\splits\corpus-splits.v1.json `
  evaluation\corpus\provisional-ablation.json `
  --repository-root .
```

manifest assignment 또는 normalization version을 바꿀 때는 이전 manifest를 보존하고
`manifest_version`을 증가시킨 뒤 변경 사유를 기록한다.

```powershell
uv run python -m evaluation.split_guard `
  C:\protected\corpus-splits.v2.json `
  evaluation\corpus\tuning-v1.json `
  C:\protected\hidden-evaluation-v1.json `
  --previous-manifest evaluation\splits\corpus-splits.v1.json `
  --repository-root .
```

hidden/private 접근과 승인 절차는
[corpus split 정책](../docs/corpus-split-policy.md)을 따른다.

## PF-003 matcher ablation

`ablation_runner.py`는 Exact+Alias 기준선, matcher별 isolated candidate, Segmented
prerequisite control, 현재 all-enabled를 같은 gold corpus에서 평가한다. matcher마다
TP·FP·FN, 다른 matcher와의 중복 및 고유 증분, short/max p50·p95와 Engine retained
memory를 기록한다. 재현성 확인을 위해 Koguard/Python 버전, profile 설정 hash, 원문을
노출하지 않는 workload 길이·SHA-256도 함께 남긴다.

```powershell
uv run python -m evaluation.ablation_runner `
  --corpus evaluation\corpus\provisional-ablation.json `
  --output evaluation\results\provisional-ablation-windows-python311.json `
  --iterations 100 `
  --warmups 10
```

현재 corpus와 결과는 구현 경로를 검증하는 `provisional-regression`이다. 서비스 정확도나
balanced profile 포함 여부는 [PF-003 기준선](../docs/matcher-ablation-baseline.md)에 적힌
한계대로 PF-005 독립 corpus 재측정 전까지 확정하지 않는다. report schema는
`ablation-report.schema.json` version 1이다.

## 비교 계약

- Koguard profile은 현재 모든 matcher를 명시적으로 켠 `current-all-enabled`이다.
- Korcen profile은 `korcen.check(text, foreign=False)`를 호출하는 `korean-all`이다.
- `review` label은 자동 평가에서 제외하고 제외 건수를 리포트한다. 평가 가능한 case가
  하나도 없으면 빈 지표를 만들지 않고 실패한다.
- detector가 반환한 값은 prediction으로만 취급하며 gold label이나 expected match를
  수정할 수 없다.
- 실제 matcher/threshold 및 `foreign` 설정을 detector별 `settings`에 기록하고
  configuration fingerprint 계산에도 포함한다.
- 리포트에는 corpus 원문, gold canonical term, detector canonical term을 남기지 않는다.
  case ID, slice, 판정, 건수, 집계 지표만 기록한다.
- Korcen 1.0.3은 boolean 판정만 제공하므로 sentence 지표만 계산한다. span/canonical
  occurrence 지표는 추정하지 않고 `unsupported`로 기록한다.

리포트 계약은 `comparison-report.schema.json`의 schema version 1로 고정되어 있다.

## Korcen 고정 배포물

PF-002의 비교 대상은 PyPI의 다음 wheel 하나로 제한한다.

| 항목 | 값 |
| --- | --- |
| 프로젝트 | <https://pypi.org/project/korcen/1.0.3/> |
| 파일 | `korcen-1.0.3-py3-none-any.whl` |
| SHA-256 | `5139fb973ab40f2f4caaa722c97553397993e6a83a463a1098a85061834fb446` |
| profile | `korean-all` (`foreign=False`) |

`make_korcen_spec`은 파일명에 의존하지 않고 wheel METADATA의 package/version과 파일
전체 SHA-256을 검증한다. 다른 Korcen 버전이나 다시 만든 wheel은 비교 대상으로
자동 수용하지 않는다.

## 환경 준비

먼저 현재 Koguard wheel을 빌드한다.

```powershell
uv sync --all-extras --dev
uv build
```

Korcen은 별도 Python 3.11 환경에 설치한다. 공식 wheel 다운로드와 의존성 설치는
평가 전 준비 단계이며, 비교 러너 자체는 다운로드나 설치를 수행하지 않는다.

```powershell
uv venv --python 3.11.9 .venv-korcen
uv pip install --python .venv-korcen\Scripts\python.exe better-profanity==0.7.0 colorama==0.4.6 C:\artifacts\korcen-1.0.3-py3-none-any.whl
```

Korcen의 직접 의존성에는 고정 버전 제약이 없으므로, 러너는 실제 설치된
`better-profanity`와 `colorama` 버전을 결과에 기록한다. 결과를 재현할 때는 wheel hash,
Python/OS, 이 두 의존성 버전, profile, corpus/configuration hash가 모두 같은지 확인한다.

## 실행

```powershell
uv run python -m evaluation.comparison_runner `
  --corpus tests\fixtures\corpus_validation\valid\public-regression.json `
  --koguard-wheel dist\koguard-0.1.0-py3-none-any.whl `
  --koguard-profile current-all-enabled `
  --korcen-wheel C:\artifacts\korcen-1.0.3-py3-none-any.whl `
  --korcen-python .venv-korcen\Scripts\python.exe `
  --output comparison-report.json
```

Koguard interpreter를 별도로 지정해야 한다면 `--koguard-python`을 사용한다. profile
인자는 이후 기본 profile을 추가할 공개 경로이며 현재는 `current-all-enabled`만 허용한다.
두 detector는 각 interpreter의 isolated mode(`-I`)와 UTF-8 mode(`-X utf8`)에서
실행되고, 지정된 wheel을 `sys.path` 선두에 넣어 평가한다. worker protocol 자체도 UTF-8
bytes로 고정해 Windows 시스템 코드페이지가 한국어 입력을 바꾸지 못하게 한다. worker가
import 중 출력한 stdout/stderr는 corpus 유출과 프로토콜 오염을 막기 위해 메모리에
보관하지 않고 버리며, 그 발생 여부만 `suppressed_output`으로 기록한다.

## 실패와 보안 경계

- artifact hash/package/version 불일치, case ID 누락·중복·추가, capability와 output의
  불일치는 즉시 실패한다.
- worker 예외는 stage와 예외 타입만 부모 프로세스에 전달한다. 예외 메시지나 corpus
  원문은 리포트에 쓰지 않는다.
- isolated mode는 Python import 환경을 분리하지만 OS sandbox는 아니다. 신뢰할 수 없는
  임의 wheel 실행 수단으로 사용해서는 안 된다.
- 작은 공개 fixture는 실행 계약 검증용일 뿐 실제 서비스 정확도 결론을 내릴 corpus가
  아니다. PF-003 이후 corpus 확장 전에는 두 제품의 우열을 수치로 일반화할 수 없다.
