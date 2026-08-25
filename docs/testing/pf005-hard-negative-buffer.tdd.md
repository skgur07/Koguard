# PF-005 hard-negative 중심 review buffer TDD 기록

## 문제

기존 balanced intake는 정확히 2,500건이고 완료 목표도 positive 500건과 hard-negative 2,000건의
합 2,500건이다. 독립 판정에서 review가 남는 정상적인 상황을 허용하려면 최소 1,000건의 추가
review 여유가 필요하다. 새 외부 source를 도입하면 권리·독립성 검토가 다시 필요하므로 먼저
기존 고정 source의 다음 deterministic rank와 Koguard 직접 작성 사례를 사용한다.

## RED

- 기존 source intake와 direct 또는 NFKC+casefold가 같은 문장이 buffer에 들어가는 실패 테스트
- 기존 제외 뒤 quota를 채우지 못하면 조용히 축소하지 않고 실패하는 테스트
- source share 30% 상한과 `300/300/300/100` quota를 고정하는 테스트
- upstream label을 gold로 오인하지 않고 모든 생성 case를 `review`로 유지하는 테스트
- 공개 report에 원문·case ID·canonical term·reviewer ID가 없는지 확인하는 테스트
- 기존 curated 250건과 겹치지 않는 hard-negative-target 100건 생성 테스트

## GREEN

- 기존 revision·artifact·license hash를 그대로 사용하는 확장 source spec 3개를 추가했다.
  - Curse: label `0` 500→800, label `1` 2,000 유지
  - KOTE: unlabelled 750→1,050
  - BEEP: `none` 250→550, `hate`·`offensive` 각 250 유지
- `curated_policy_intake --kind hard-negative-buffer`가 기존 250건과 겹치지 않는 프로젝트 작성
  100건을 생성한다.
- `review_buffer_planner`가 확장 source와 기존 source intake를 쌍으로 검증하고 기존 direct·
  NFKC+casefold 중복 및 source 간 중복을 제거한다.
- 선택 ID는 원래 source ID를 노출하지 않는 buffer-specific opaque SHA-256 ID로 다시 만든다.
- 원문 corpus는 보호 경로에만 쓰고 CLI와 공개 report는 aggregate만 출력한다.

## 생성 결과

| source | 확장 available | 기존 제외 | 선택 | share |
| --- | ---: | ---: | ---: | ---: |
| Curse-detection-data | 2,800 | 2,500 | 300 | 30% |
| KOTE | 1,050 | 750 | 300 | 30% |
| Korean Hate Speech | 1,050 | 750 | 300 | 30% |
| Koguard curated | 100 | 0 | 100 | 10% |

최종 1,000건은 모두 `review`, `unadjudicated-intake`, `tuning`이고 기존 intake overlap은 0건이다.
외부 targeting label과 설계 의도는 reviewer 입력에 없으며 `upstream_labels_are_gold=false`다.
공개 집계는 `evaluation/results/pf005-hard-negative-buffer-v1.report.json`에 저장한다.

## 해석 제한

- hard-negative-target 근거가 있는 것은 Curse 300, BEEP 300, curated 100의 700건이다.
- KOTE 300건은 source label이 없는 독립 분포 보강이며 hard-negative라고 가정하지 않는다.
- 1,000건 모두 독립 이중 판정과 불일치 제3 판정 전에는 gold가 아니다.
- BEEP 원문과 파생 annotation의 CC-BY-SA-4.0 attribution·share-alike 경계 및 수동 privacy 검토는
  계속 완료 blocker다.

## 검증 명령

```powershell
uv run python -m evaluation.corpus_intake <buffer-source-spec> <pinned-artifact> --output <protected> --report <aggregate>
uv run python -m evaluation.curated_policy_intake --kind hard-negative-buffer
uv run python -m evaluation.review_buffer_planner evaluation/compositions/pf005-hard-negative-buffer.v1.json --output <protected> --report evaluation/results/pf005-hard-negative-buffer-v1.report.json
uv run python -m evaluation.corpus_validator <protected-buffer>
uv run pytest
```
