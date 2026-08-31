# Koguard 평가 러너

이 디렉터리의 비교 러너는 PF-001 corpus의 동일한 gold annotation을 Koguard와
Korcen에 각각 입력하고, 문장 단위 및 가능한 범위의 occurrence 단위 지표를 JSON으로
기록한다. 평가 대상 패키지는 코어 런타임 의존성에 추가하지 않으며, 네트워크 접근도
러너 밖에서만 수행한다.

## PF-006 dictionary provenance validator

`dictionary_provenance.py`는 packaged literal·Alias와 `dictionary-provenance.v1.json`을
양방향으로 비교한다. normalized 중복, Alias canonical 충돌, core 포함 hard-negative,
미승인 review·license, 재배포 불가 source, AI 후보의 packaged 승격과 평가 근거 누락을 차단한다.

```powershell
uv run python -m evaluation.dictionary_provenance
```

manifest schema, core/AI 경계, 승격 순서와 변경 기록은
[사전 후보 provenance 정책](../docs/dictionary-provenance.md)을 따른다. validator는 네트워크를
사용하지 않으며 오류에 surface를 출력하지 않는다. manifest와 validator는 sdist·CI 전용이고
wheel 런타임 데이터에는 포함하지 않는다.

## PF-005 license-pinned review intake

`corpus_intake.py`는 외부 자료를 다운로드하지 않고 `sources/*.json`에 고정한 revision,
artifact SHA-256, LICENSE SHA-256과 형식을 검증한다. source spec v2는 UTF-8 구분자 파일,
header 유무, label strata 또는 전체 quota, MIT·Apache-2.0·CC-BY·CC-BY-SA source를 닫힌
계약으로 다룬다. 현재 2runo 2,500건, KOTE 750건, Korean Hate Speech 750건을 생성한다.

upstream label은 Koguard gold가 아니므로 새 source case는 모두 tuning `review`이며 exact
span이나 실제 평가 slice를 갖지 않는다. source별 report는 `gold_ready=false`를 고정한다.
`curated_policy_intake.py`는 100개 positive-target 정책 문맥과 150개 hard-negative-target
유사 표기를 직접 작성하지만, 설계 의도가 gold를 대신하지 않도록 역시 blinded review로 만든다.
`--kind hard-negative-buffer`는 기존 curated intake와 겹치지 않는 hard-negative-target 100건을
추가로 만든다.

`corpus_composer.py`는 첫 batch 확정 92건을 우선 보존하고 2runo/KOTE/Korean Hate Speech/
Koguard curated를 `750/750/750/250`으로 선택한다. 직접·NFKC+casefold 중복을 제거하고 source
비중 30% 상한을 강제한다. balanced 원문은 보호 경로에만 두며 공개 report에는 aggregate만 남긴다.
현재 상태와 남은 판정 작업은
[PF-005 corpus 상태](../docs/corpus-intake-status.md)에 기록한다. 생성 원문은 수동 privacy
review 전까지 Git과 배포물에 포함하지 않는다.

```powershell
uv run python -m evaluation.curated_policy_intake

uv run python -m evaluation.corpus_composer `
  evaluation\compositions\pf005-balanced-review-intake.v1.json `
  --output evaluation\corpus\tuning\pf005-balanced-review-intake-v1.json `
  --report evaluation\results\pf005-balanced-review-intake-v1.report.json
```

기존 2,500건의 unresolved 여유를 확보하려면 고정 source artifact에서 더 큰 intake를 생성한 뒤
`review_buffer_planner.py`로 기존 source intake를 제외한다. PF-005 buffer v1은 Curse/KOTE/BEEP/
Koguard curated를 `300/300/300/100`으로 선택하고 direct·NFKC+casefold 기존 overlap 0건과
source 30% 상한을 강제한다. Curse `0`, BEEP `none`, curated 설계는 hard-negative 가능성이 높은
후보 targeting일 뿐이며 모든 생성 label은 `review`, `upstream_labels_are_gold=false`다.

```powershell
uv run python -m evaluation.curated_policy_intake --kind hard-negative-buffer

uv run python -m evaluation.review_buffer_planner `
  evaluation\compositions\pf005-hard-negative-buffer.v1.json `
  --output evaluation\annotation-work\pf005-hard-negative-buffer-v1.json `
  --report evaluation\results\pf005-hard-negative-buffer-v1.report.json
```

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

남은 review를 단순 ID 순서로 자르지 않고 출처별로 균형 있게 선택하려면 보호 corpus에서 다음
명령을 실행한다. 선택은 source별 stable SHA-256 rank를 round-robin하며 detector prediction,
upstream label, 기존 확정 label을 사용하지 않는다. 후속 batch는 이전 queue를 반복 가능한
`--exclude-corpus`로 전달해 stable ID와 원문·출처·라이선스·split 일치를 확인한다. queue corpus가
남아 있지 않은 과거 batch는 `--exclude-annotation-batch`로 case ID·원문과 source corpus ID를
결속해 이미 검토한 case를 제외한다. 서로 다른 두 exclusion 형식의 과거 교집합은 별도 집계하고
합집합을 제외한다. 이는 reviewer 구성 편향과 중복을 줄이는 queue일 뿐 hard-negative label을
보장하지 않는다.

```powershell
uv run python -m evaluation.review_queue_planner <protected-corpus> `
  --queue-id pf005-balanced-batch-002 `
  --corpus-id koguard-pf005-balanced-batch-002-review-queue `
  --exclude-corpus <previous-protected-queue> `
  --exclude-annotation-batch <previous-protected-annotation-batch> `
  --limit 500 --output <protected-queue> --report <protected-report>
```

matcher 증분 또는 특정 profile의 문장 FP가 annotation 정책과 충돌할 가능성이 있으면 해당
case만 이전 판정값 없이
재감사한다. `prepare`는 report의 corpus ID와 canonical SHA-256 결속을 확인하고 이전
label·span·slice를 제거한다. `apply`는 원문·출처·라이선스·split이 바뀌지 않았는지 검증하고
독립 판정의 결정 필드만 반영한다. 두 명의 reviewer와 제3 adjudicator 절차는 기존 annotation
workflow를 그대로 사용한다.

```powershell
uv run python -m evaluation.reaudit_workflow prepare <protected-corpus> <protected-ablation> `
  --matcher choseong --corpus-id koguard-pf005-choseong-fp-reaudit-v1 `
  --output <protected-reaudit-corpus> --report <protected-report>

uv run python -m evaluation.reaudit_workflow prepare <protected-corpus> <protected-ablation> `
  --profile exact-alias --corpus-id koguard-pf005-common-exact-fp-reaudit-v1 `
  --output <protected-reaudit-corpus> --report <protected-report>

uv run python -m evaluation.reaudit_workflow apply <protected-corpus> `
  <protected-prepared-reaudit> <protected-adjudicated-reaudit> `
  <protected-adjudication-report> --output <protected-updated-corpus> `
  --report <protected-apply-report>
```

```powershell
uv run python -m evaluation.annotation_workflow export `
  evaluation\corpus\tuning\pf005-balanced-review-intake-v1.json `
  --annotation-set-id pf005-balanced-batch-001-primary `
  --reviewer-id reviewer-a `
  --offset 0 `
  --limit 500 `
  --output evaluation\annotation-work\pf005-balanced-batch-001-primary.json

uv run python -m evaluation.annotation_workflow export `
  evaluation\corpus\tuning\pf005-balanced-review-intake-v1.json `
  --annotation-set-id pf005-balanced-batch-001-secondary `
  --reviewer-id reviewer-b `
  --offset 0 `
  --limit 500 `
  --output evaluation\annotation-work\pf005-balanced-batch-001-secondary.json

uv run python -m evaluation.annotation_workflow merge `
  evaluation\corpus\tuning\pf005-balanced-review-intake-v1.json `
  evaluation\annotation-work\pf005-balanced-batch-001-primary.json `
  evaluation\annotation-work\pf005-balanced-batch-001-secondary.json `
  --output evaluation\annotation-work\pf005-balanced-after-batch-001.json `
  --report evaluation\annotation-work\pf005-balanced-batch-001.report.json
```

두 검토자의 판정이 다른 case는 동일 범위로 내보낸 세 번째 batch에서만 판정한다. 최초 두
검토자가 합의한 case는 세 번째 batch의 초기 `pending` 상태를 유지해도 되며, 불일치 case는
`approved` 후 최종 label·span·canonical term·slice를 기록하거나 `review`로 명시적으로
유보한다. `adjudicate`는 세 reviewer와 annotation set ID가 모두 다른지 확인한다.

```powershell
uv run python -m evaluation.annotation_workflow adjudicate `
  evaluation\corpus\tuning\curse-review-intake-v1.json `
  evaluation\annotation-work\pf005-batch-001-primary.json `
  evaluation\annotation-work\pf005-batch-001-secondary.json `
  evaluation\annotation-work\pf005-batch-001-adjudicator.json `
  --output evaluation\annotation-work\pf005-after-batch-001.adjudicated.json `
  --report evaluation\annotation-work\pf005-batch-001.adjudicated.report.json
```

`annotation-batch.schema.json`과 `annotation-report.schema.json`이 공개 작업 계약이다. merge
report의 선택적 `adjudication_counts`는 불일치 판정 대상·해결·유보·privacy 제외 건수만
공개한다. `gold_ready=false`는 batch 합의만으로 PF-005 전체 규모, 출처 편향과 hidden
evaluation 조건을 충족했다고 오인하지 않도록 고정한다.

## PF-007 false-negative candidate evaluation

`fn_candidate_evaluation.py`는 provenance manifest에서 권리·독립 판정이 승인된 exact literal
`candidate`만 선택해 현재 packaged 기본 사전과 비교한다. 보호 tuning corpus의 원문·case ID·
canonical term은 report에 기록하지 않고 candidate ID, 입력 hash, positive/hard-negative support,
문장 및 exact occurrence 증분만 공개한다.

```powershell
uv run python -m evaluation.fn_candidate_evaluation `
  evaluation\annotation-work\pf005-after-batch-001.adjudicated.json `
  evaluation\dictionary-provenance.v1.json `
  --output evaluation\annotation-work\pf007-top-candidates.report.json
```

`tuning_gate_passed`는 hidden evaluation이나 packaged 승격 완료가 아니다. candidate별 positive
support 1건 이상, hard-negative 2건 이상, occurrence TP 순증가와 sentence FP 무증가를 뜻한다.
결합 결과와 개별 gate가 모두 통과하고 hidden 평가까지 확인된 후보만 별도 변경에서 승격한다.

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

## PF-014 hidden evaluation 공개 집계

hidden 원문과 `ablation_runner`의 case-level 결과는 저장소 밖 보호 환경에만 둔다. corpus
custodian은 고정 release commit에서 split guard 누출 0건을 확인하고 protected ablation을
생성한 뒤, corpus hash·건수·manifest version·독립 합의·privacy·rights 검토와 서로 다른 두
승인을 `hidden-evaluation-attestation.schema.json` 계약으로 묶는다.

`hidden_evaluation_report.py`는 보호 ablation과 attestation hash가 일치하는지 확인하고
`strict`·`balanced`·`aggressive` 전체 지표와 balanced slice 집계만 allowlist로 내보낸다.
case ID, 원문, canonical term, reviewer ID와 실패 사례 목록은 공개 report에 포함하지 않는다.

```powershell
uv run python -m evaluation.hidden_evaluation_report `
  --source-ablation C:\protected\pf014-hidden-v1.ablation.json `
  --attestation C:\protected\pf014-hidden-v1.attestation.json `
  --output C:\handoff\pf014-hidden-v1.aggregate.json
```

attestation은 `release_commit`, protected ablation SHA-256, corpus SHA-256과 건수, split manifest
version, 고정 normalization version, direct/normalized leak 0건을 함께 고정한다. 확정 positive와
hard-negative가 모두 있고 review가 0건이며 annotation·privacy·rights와 두 역할의 독립 승인이
완료된 경우에만 `gold_ready=true` report를 만들 수 있다.

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

## PF-009 공개 profile 평가 보고서

`profile_report.py`는 보호된 PF-005 ablation에서 `exact-alias`, `choseong`, `all-enabled`를
각각 공개 `strict`, `balanced`, `aggressive`로 검증해 매핑한다. 원문, case ID, canonical
표현과 slice별 결과는 복사하지 않고 설정·전체 정확도·성능 집계만 allowlist로 출력한다.

```powershell
uv run python -m evaluation.profile_report `
  --source-ablation C:\protected\pf005-balanced-review-intake.v1.ablation.json `
  --output evaluation\results\pf009-profile-evaluation.report.json
```

공개 보고서는 원본 ablation과 corpus SHA-256, 환경, 세 profile 집계, balanced 증분과 임시
FP·p95 게이트를 기록한다. 2026-08-28 중복 없는 batch-004와 공통 Exact/Alias FP 1건의
블라인드 재감사를 반영한 최종
수량 기준 표본은 2,763건(positive 639, hard-negative 2,124)이다. strict와 balanced의 문장
TP/FP/FN/TN은 각각 416/0/223/2,124와 440/0/199/2,124이며 balanced 문장 recall은 68.9%다.
초성 occurrence FP 후보 7건을 다시 이중 검토한 뒤 balanced occurrence TP/FP/FN은
584/39/390, recall 60.0%로 strict보다 TP 30건과 FP 2건이 늘었다. 전체 FP 증분 0 gate는 계속
실패한다. short-chat p95는 0.0242ms, 최대 입력 p95는 5.2255ms였다. 입력에서 review 737건을
제외했으므로 실서비스 FP나 최종 recall로 일반화할 수
없고, 성능은 세 OS CI에서 다시 확인해야 한다. 계약은
`profile-report.schema.json` version 1이다.

남은 review를 편향 없는 정확도 표본으로 가장하지 않고 부족 slice 후보만 우선 확인하려면
`review_queue_planner.py`에 `--surface-priority`를 지정한다. 이 모드는 detector prediction,
upstream label, 기존 판정을 사용하지 않고 Jamo·초성 연속·반복 문자·한글 사이 separator/gap·
ASCII token 같은 표면 신호를 source round-robin 안에서 먼저 배치한다. 생성 queue는 targeted
slice discovery 전용이며 일반 정확도 추정에는 사용하지 않는다.

첫 surface-priority 120건은 독립 이중 검토와 제3 재심 뒤 positive 26건, hard-negative 63건,
review 31건으로 남았다. 초기 합의는 27건, 불일치는 93건이었고 재심은 그중 80건을 해결했다.
확정 89건은 `pf005-slice-coverage.report.json`의 `targeted_supplement`와
`combined_slice_coverage`에서만 보강 근거로 표시한다. profile의 corpus 건수·정확도 지표는
바꾸지 않으며 공개 annotation 리포트에도 원문·case ID·canonical·reviewer ID를 넣지 않는다.

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

## PF-012 Unicode hardening 보고서

공개 Unicode 회귀 20건의 slice별 TP·FP·FN과 `balanced` 최대 입력 적대 workload의
p50·p95·peak allocation은 별도 경량 runner로 함께 측정한다. 성능만 좋아지고 탐지가 꺼진
결과를 허용하지 않도록 각 workload에 수정 후 기대 match count와 실제 count를 기록한다.

```powershell
uv run python -m evaluation.unicode_hardening_report `
  --iterations 100 `
  --warmups 10 `
  --output evaluation/results/pf012-local.json
```

고정 전후 결과와 해석은 [`../docs/unicode-fp-hardening.md`](../docs/unicode-fp-hardening.md)를
따른다. 이 공개 synthetic corpus는 결정적 회귀용이며 hidden 실서비스 평가를 대체하지 않는다.
