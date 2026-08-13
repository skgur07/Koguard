# 사전 후보 provenance와 승격 정책

이 문서는 packaged lexical core와 향후 후보 데이터를 같은 manifest에서 추적하되, 검토되지
않은 후보가 `badwords.txt` 또는 `aliases.tsv`에 들어가지 못하게 하는 PF-006 계약이다.

## 파일과 책임

| 파일 | 책임 |
| --- | --- |
| `evaluation/dictionary-provenance.v1.json` | packaged term·Alias와 후보의 출처·권리·판정·검토 상태 |
| `evaluation/dictionary-provenance.schema.json` | 닫힌 JSON schema와 허용 enum |
| `evaluation/dictionary_provenance.py` | manifest와 실제 packaged data의 완전 대응 검증 |
| `docs/dictionary-data-changelog.md` | 후보 승격·제외와 증분 평가 결과 기록 |
| `src/koguard/data/NOTICE.md` | 배포물의 외부 출처와 라이선스 고지 |

validator는 네트워크에 접근하지 않는다. 원격 저장소나 라이선스 문서는 먼저 고정 revision과
검토 근거로 기록하고, 로컬 manifest와 packaged file만 비교한다. manifest와 validator는
source distribution과 CI에는 포함하지만 런타임에 필요하지 않으므로 wheel에는 넣지 않는다.

## 대상 계층

- `core`: 승인 후 문맥과 무관한 lexical 탐지에 사용한다. 등록 표현 또는 승인 Alias가
  복합어·인용·사용자명·게임 문맥에 있어도 core positive다.
- `ai-candidate`: 신조어, 암시적 공격과 문맥 추론을 향후 선택적 post-core 단계에서 평가하기
  위한 후보다. `status=packaged`로 승격할 수 없고 core 결과를 취소하는 용도로 사용하지 않는다.

Whitelist는 manifest 후보나 label을 바꾸지 않는다. 사용자가 지정한 겹치는 결과 구간만
명시적으로 보호한다.

## 후보 상태

| 상태 | 의미 |
| --- | --- |
| `candidate` | 검토 또는 평가 중이며 배포 사전에 없음 |
| `packaged` | 모든 승격 게이트를 통과해 배포 사전에 있음 |
| `rejected` | 제외 근거를 남기고 승격하지 않음 |

`classification`은 `positive`, `hard-negative`, `review` 중 하나다. 등록 core literal을 실제로
포함한 문자열은 문맥을 이유로 `hard-negative`가 될 수 없다. 그런 substring 정책 위반은
validator가 차단한다. Alias는 `exact_token`·`token_prefix` 경계를 포함한 matcher 회귀와
`evaluation_refs`로 판정한다.

## packaged 승격 게이트

`packaged` 후보는 다음을 모두 만족해야 한다.

1. `target_layer=core`, `classification=positive`, `review.status=approved`
2. 승인 결정 근거와 하나 이상의 평가·회귀 참조 보유
3. source의 `license_status=approved`, `redistribution_allowed=true`
4. NFKC normalized surface·canonical 값이 manifest 선언과 일치
5. normalized surface 중복과 candidate ID 중복이 없음
6. Alias canonical이 packaged literal로 존재하고 `aliases.tsv`의 mode·canonical과 일치
7. manifest의 packaged literal·Alias와 실제 `badwords.txt`·`aliases.tsv`가 빠짐없이 일치

미확인 라이선스 자료는 `license_status=pending`, `status=candidate`로만 둘 수 있다. 권리 검토가
끝났더라도 기존 pending source를 제자리에서 바꾸지 말고, 승인 근거가 포함된 새 source revision을
추가한다.

## 변경 절차

1. 후보와 source revision, license, 대상 계층을 manifest에 `candidate`로 추가한다.
2. tuning corpus에서 positive와 등록 표현이 없는 hard-negative를 검증한다.
3. 독립 consensus 또는 명시된 review 근거를 기록한다.
4. `docs/dictionary-data-changelog.md`에 변경 전후 TP·FP·FN report 경로와 판정을 남긴다.
5. 승인된 경우에만 packaged file과 manifest status를 같은 커밋에서 바꾼다.
6. validator, 전체 corpus 평가, 품질 게이트와 artifact 내용을 확인한다.

```powershell
uv run python -m evaluation.dictionary_provenance
```

성공 출력은 source·candidate·packaged·pending 집계만 포함한다. 실패 출력은 파일 위치와
candidate ID만 사용하며 candidate surface나 corpus 원문을 반복 출력하지 않는다.
