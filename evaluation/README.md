# Koguard 평가 러너

이 디렉터리의 비교 러너는 PF-001 corpus의 동일한 gold annotation을 Koguard와
Korcen에 각각 입력하고, 문장 단위 및 가능한 범위의 occurrence 단위 지표를 JSON으로
기록한다. 평가 대상 패키지는 코어 런타임 의존성에 추가하지 않으며, 네트워크 접근도
러너 밖에서만 수행한다.

## PF-005 license-pinned review intake

`corpus_intake.py`는 외부 자료를 다운로드하지 않고 `sources/*.json`에 고정한 revision,
artifact SHA-256, LICENSE SHA-256과 형식을 검증한다. 현재 MIT
`2runo/Curse-detection-data` 5,825건 중 source label strata `0:500`, `1:2,000`을
deterministic SHA-256 rank로 선택했다.

upstream label은 Koguard gold가 아니므로 생성된 2,500건은 모두 tuning `review`이며 exact
span이나 실제 평가 slice를 갖지 않는다. `results/curse-review-intake-v1.report.json`은
`gold_ready=false`를 고정한다. 현재 상태와 남은 판정 작업은
[PF-005 corpus 상태](../docs/corpus-intake-status.md)에 기록한다. 생성 원문은 수동 privacy
review 전까지 Git과 배포물에 포함하지 않는다.

## PF-005 rights-pending quarantine intake

`quarantine_intake.py`는 권리 검토가 끝나지 않은 복합 출처를 공개 corpus와 분리해 분석한다.
ZIZUN 고정 artifact 10,000행에서 Curse 원본과의 normalized overlap 2,010건, 민감 패턴 1건,
정규화 중복 12건을 제외하고 source label별 250건씩 총 500건을 deterministic하게 선택했다.

이 500건은 모두 `review`이며 `redistribution_allowed=false`, `independent_source_ready=false`,
`gold_ready=false`다. 원문 queue는 `evaluation/quarantine/`에 생성되어 Git과 sdist에서 제외되고,
source pin과 원문 없는 집계 report만 보존된다. 실행 전에 운영자가 고정 dataset, LICENSE,
README와 Curse exclusion 원본을 별도로 준비해야 하며 runner는 네트워크에 접근하지 않는다.

```powershell
uv run python -m evaluation.quarantine_intake `
  evaluation\sources\candidates\zizun-korean-malicious-comments.v1.json `
  C:\artifacts\zizun-Dataset-50b92f50.csv `
  C:\artifacts\zizun-LICENSE-50b92f50.txt `
  C:\artifacts\zizun-README-50b92f50.md `
  --exclusion C:\artifacts\curse-detection-data-ff241621.txt `
  --output evaluation\quarantine\zizun-review-intake-v1.json `
  --report evaluation\results\zizun-quarantine-intake-v1.report.json
```

사용 내역과 권리 blocker는
[외부 평가 자료 사용·권리 감사 대장](../docs/source-rights-audit.md)을 따른다.

## PF-005 blinded annotation workflow

`annotation_workflow.py`는 tuning `review` case를 stable ID 순서로 최대 500건씩 export하고,
서로 다른 opaque reviewer ID로 작성한 두 annotation batch를 비교한다. export에는 원문과 빈
annotation 필드만 있으며 upstream label, Koguard/Korcen prediction, 기존 gold는 포함하지 않는다.

두 검토자가 모두 `privacy_status=approved`로 표시하고 label, exact span, canonical term, slice가
일치한 case만 승격한다. 불일치, privacy `pending` 또는 `exclude`는 계속 `review`로 남는다.
batch·merge 결과 원문은 `evaluation/annotation-work/` 또는 저장소 밖의 보호 경로에 두며 이
디렉터리는 Git과 sdist에서 제외된다. report에는 원문과 canonical term 대신 집계만 저장한다.

```powershell
uv run python -m evaluation.annotation_workflow export `
  evaluation\corpus\tuning\curse-review-intake-v1.json `
  --annotation-set-id pf005-batch-001-primary `
  --reviewer-id reviewer-a `
  --offset 0 `
  --limit 100 `
  --output evaluation\annotation-work\pf005-batch-001-primary.json

uv run python -m evaluation.annotation_workflow export `
  evaluation\corpus\tuning\curse-review-intake-v1.json `
  --annotation-set-id pf005-batch-001-secondary `
  --reviewer-id reviewer-b `
  --offset 0 `
  --limit 100 `
  --output evaluation\annotation-work\pf005-batch-001-secondary.json

uv run python -m evaluation.annotation_workflow merge `
  evaluation\corpus\tuning\curse-review-intake-v1.json `
  evaluation\annotation-work\pf005-batch-001-primary.json `
  evaluation\annotation-work\pf005-batch-001-secondary.json `
  --output evaluation\annotation-work\pf005-after-batch-001.json `
  --report evaluation\annotation-work\pf005-batch-001.report.json
```

`annotation-batch.schema.json`과 `annotation-report.schema.json`이 공개 작업 계약이다. merge
report의 `gold_ready=false`는 batch 합의만으로 PF-005 전체 규모, 출처 편향과 hidden evaluation
조건을 충족했다고 오인하지 않도록 고정한다.

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
