# 원문 변경·파일에 연결된 검수

새 publication 패키지와 공고 정정 대응에서 읽는다. 기존 immutable 패키지는 보존하고 재사용한다. 이 도구는 관찰 기록·파일 무결성을 검사하며 시각 검토를 자동으로 수행했다고 주장하지 않는다.

## 원문 변경

새로 수집한 source.json마다 `content_preflight.py snapshot --source <파일> --output <새스냅샷>`을 만든다. 상세 HTML과 실제 첨부 해시를 다시 검사하며 다운로드와 판독은 구분한다. 이전 스냅샷이 있으면 `compare --before ... --after ... --output <새보고서>`로 제목·본문·접수방법/기간 필드·첨부 교체를 비교한다. 변경되면 해당 원문과 읽은 사실의 출처를 재검토한다. 변경 없음도 현재 모집완료·취소·예산소진과 30분 이내 eligibility 검사를 대신하지 않는다.

금액·대상·접수기간·활용 인정기간·신청방법·문의처는 facts에 실제 출처 페이지/표와 연결한다. source 스냅샷은 파일 확보·변경 비교 근거이며 문서 판독 완료 근거가 아니다. 보호 문서의 공식 대체본은 기존 원문 판독 절차를 따른다.

## 실제 이미지·문구 검수

전체 이미지 생성 원칙을 유지한다. 제목·핵심 혜택·필수조건·CTA의 확정 문구를 생성 전에 정하고, 생성 후 이미지에서 실제 읽은 문구와 비교한다. 100%와 360px 폭에서 오탈자·넘침·테두리 접촉·가림·시선 흐름을 확인한다. OCR 자료가 있으면 해당 이미지 해시에 연결해 보조로 대조한다. OCR 차이는 실제 시각 확인으로 판단하며 OCR을 실행하지 않았으면 실행한 것처럼 기록하지 않는다.

단일 이미지는 핵심 혜택 → 대상·기간 → 행동의 위계를 내용에 맞게 설계한다. 웹툰은 기업의 문제·질문에서 캐릭터의 선택·실험·오해 해결로 진행한다. 재치가 선정·지원 규모·신청 조건을 바꾸지 않게 한다. 연재는 앞 회차와 개념 중복·다음 회차 연결도 확인한다.

웹툰과 대화형 카드뉴스의 `layout` 검수에는 [대사 읽기 순서](dialogue-reading-order.md)를 포함한다. 컷별 선택 방향·예상 발화 순서·실제 풍선 순서·화자를 해시에 연결해 남기고, 왼쪽→오른쪽과 위→아래가 충돌하거나 질문/답변이 역순이면 수정 전 통과시키지 않는다. [반짝 웹툰](spark-webtoon.md)은 개그의 설정·오해·반전 순서로 검토하며 순수 재미물에 신청 CTA를 요구하지 않는다.

웹툰 `layout/character` 근거에는 [컷별 장면 변화](creative-variation.md#웹툰의-컷별-장면-변화) 검토도 남긴다. 같은 그림의 말풍선 교체·미세 크롭·좌우 반전만 한 장을 새 컷으로 통과시키지 않는다. 실제 장을 나란히 열어 몸·손·표정·카메라·구도의 변화가 사건과 긴장감을 진전시키는지 확인하고 반복 발견 시 새 장면으로 수정한다.

각 장의 중심 사건·감정 변화·`page_peak`를 실제 이미지와 대조한다. 특히 인접 컷의 구도·표정·몸짓을 개별 기록하고, 같은 찡그린 얼굴과 물건을 든 자세가 이어지면 새로 생성했다는 이유만으로 통과시키지 않는다. 소품·얼굴 확대만으로 극적 긴장이 충분하다고 단정하지 않는다.

최근 6개 서로 다른 공고/회차의 실제 완성본을 열어 비교한다. 색·배경만 바꾼 반복은 제외하고 서사·레이아웃·훅·카메라·행동을 비교한다. 의도한 연작 반복에는 사용자 선택 근거를 남긴다. 이전 파일이 없으면 미검증 범위를 숨기지 않는다.

작업의 검수 spec에는 다음 값을 실제 결과로 채운다:

- `source_key`, `reviewer`, `generation_method`, `expected_size`.
- `images[]`: 최종 PNG의 `path/sha256`, 실제 360px 미리보기의 `mobile_path/mobile_sha256`, 순서가 같은 `expected_text/observed_text` 문자열 배열.
- 이미지별 `reviews`: `facts/text/mobile/layout/character/brand` 각각의 `status/evidence/checked_at`. 캐릭터·기관 로고가 없을 때만 해당 항목을 `not-applicable`과 구체적인 근거로 기록한다. 실제 사람 검토가 없으면 사람 승인으로 표현하지 않는다.
- `creative.signature`: 실제 `format_id/layout_family/hook_device/character_acting`. `creative.recent[]`에는 다른 source_key, 실제 `preview_path/sha256`, 이전 signature와 `review_evidence`를 최신순으로 둔다. `difference_evidence`에 실제 차이를 남기고 첫 제작·과거 파일 부재는 `no_history_evidence`로 설명한다.

**지원사업 길찾기 9~34화**에는 `education_review`도 기록한다. `level`은 `standard`(5장), `expanded`(6장), `complex`(7장) 중 고르고 `page_count_reason`에 실제 설명 단계 수를 적는다. `pages`는 이미지 순서대로 `page`(1부터), `role`(첫 장 `question`, 가운데 `explain`·`example`·`compare`·`check`, 마지막 `apply`), `takeaway`(해당 장에서 새로 알게 되는 한 문장)를 넣는다. `plain_language_evidence`에 실제 360px 이미지를 읽고 풀어 쓴 용어와 설명 흐름을 기록한다. `reader_checks`에는 `kind`가 `explain`, `apply`인 질문을 하나씩 두고 `question`, `answer`, `pages`(답을 찾을 장 번호)를 적는다. 검사는 장수, 누락, 동일 이미지 반복과 기록 형식을 확인하며, 9화 이후 가운데 장에 `explain`과 `example`이 각각 있어야 한다. 게시 게이트에서 검수에 사용한 이미지 순서와 manifest의 실제 게시 순서를 대조한다. 이해도 판단은 실제 장을 읽은 모델 검수로 남긴다.

`content_preflight.py review --spec <파일> --output <새보고서>`는 PNG를 실제 디코딩하고 크기·파일 해시·문구 대조·구성 반복·근거 필드를 확인한다. Pillow가 있는 기존 이미지/QR 환경을 사용한다. 의존성이 없거나 이미지가 손상되면 통과를 기록하지 않는다. 새 job의 `runtime_contract_version=1`, `quality_review_path`, `final_image_paths`, `creative_signature`에 연결하면 `validate_publication.py`가 spec과 실제 파일을 재검사한다. 선언 검사는 사람이 읽은 사실을 자체 증명하지 않는다.

## CI·QR의 정확한 영역 교체

전체 포스터는 이미지 생성 도구로 만든다. `asset_regions.py`는 기존 사용자 지정으로 QR 또는 로고 영역만 정확히 교체해야 할 때 사용한다. 이 도구를 일반 문자 조판이나 포스터 전면 편집으로 확대하지 않는다.

`config/region-authorizations.json` 또는 작업별 grant에서 이번 공고·영역에 적용되는 실제 사용자 승인을 확인한다. 확인한 범위는 재사용한다. 로고는 해당 작업의 사용자 지정과 CI registry의 정확한 원본 해시를 작업별 grant 사본의 `brand_assets`에 연결한다.

보정 입력 JSON의 `regions` 배열에는 `kind=qr|logo`, `[x,y,width,height]`의 `rect`, `asset_path`, `asset_sha256`를 기록한다. 필요할 때만 해당 영역을 지울 `background_rgba`를 지정한다. grant에는 `id/active/source_keys/regions/user_request_evidence`가 필요하며 특정 완성본 지정이면 `base_sha256`으로 한정한다.

```powershell
python scripts/asset_regions.py --base <원본PNG> --source-key <공고키> --regions <영역JSON> --grants <허용근거JSON> --output <새개정PNG> --report <새보고서>
```

원본은 보존하고 영역 밖의 모든 RGBA 픽셀 동일성을 확인한다. 로고는 등록 원본 비율을 유지한다. 최종 보정본은 전체 이미지 검수와 QR 독립 해독을 다시 수행한다. 보정 보고서의 `final_qr_decode_verified=false`는 스캔 검사 완료를 뜻하지 않는다. 단축주소 오류에 대비한 서비스 대안은 게시 전 제작 단계의 대안이며 이미 배포한 QR이 자동으로 바뀌는 기능은 아니다.
