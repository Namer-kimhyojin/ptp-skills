# QR코드로 상세 공고 연결

## 현재 단축주소 기본값

`config/link-policy.json`의 `short-preferred`는 **사업공고·기관소개·연재 웹툰 모두** 적용한다. 검증된 원래 공식 URL → 단축주소 발급/재사용 및 리디렉션 확인 → 단축주소 QR 생성 → 전체 이미지 생성 → 실제 최종 이미지의 QR 해독 순서다. 단축주소를 확정하기 전에 긴 원문 QR을 생성 참조로 넣지 않는다. 기관소개·직원안내는 `--purpose institution`을 지정한다. 도구의 기본 `notice` 모드는 기존 사업공고 주소 제한을 유지한다.

작업 `qr`에 `link_policy_version`, `official_url`, `target_url`(실제 QR 값), `short_link_report`, `visible_short_url`, `visible_short_url_review`, 최종 해독 `report_path`를 기록한다. 단축주소는 이미지에서 읽을 수 있게 표기하고 QR과 문자 주소가 같은지 실제로 확인한다. 기존 주소는 `--reuse-report`로 리디렉션 재확인 후 재사용한다. `validate_publication.py`가 정책 미적용·긴 주소 잔존·목적지 불일치·최종 이미지 해시 변경·원본/0.5배 해독 누락을 차단한다. 이 선언 검사는 실제 화면의 문자열 판독·게시 직전 리디렉션 재확인을 대신하지 않는다.

## 기본 적용

사업공고 카드뉴스와 SNS툰의 **마지막 CTA 장에 QR 1개를 기본 포함**한다. 연결 대상은 수집 단계에서 확인한 해당 공고의 공개 HTTPS 상세 주소다. 별도로 제외 요청을 받았거나 지면에서 가독성을 확보할 수 없다면 텍스트 경로를 남기고 제외 사유를 기록한다. 출처 링크가 준비되지 않았을 때 임의의 링크로 대체하지 않는다.

사용자가 QR을 명시적으로 요구한 작업에서는 먼저 QR 전용 CTA 장을 추가하거나 배치를 바꿔 가독성을 확보한다. 해결되지 않으면 QR 작업이 미완료임을 알리고, 제외한 상태를 요청 충족으로 처리하지 않는다.

- 공고 상세 페이지 QR의 라벨은 **`상세 공고 보기`**다. 공고 상세 페이지로 연결하면서 `바로 신청`·`신청서 제출`이라고 표시하지 않는다. 게시물에서 실제 온라인 신청 방식과 로그인 조건은 별도 안내한다.
- 로그인 URL, 토큰·인증코드·세션정보가 포함된 주소, 개인정보가 포함된 링크는 사용하지 않는다. 작업에서 확인한 공식 공개 주소만 단축하며 임의 추적 매개변수는 추가하지 않는다.
- URL의 공개 접근 여부·본문·현재 접수 상태·정정 여부를 게시 직전 브라우저/수집 단계에서 확인한다. QR 생성 도구는 네트워크에 접속하지 않으므로 생성 성공을 링크의 유효성 검증으로 간주하지 않는다.
- 기초 URL은 `https://www.ptp.or.kr/main/board/view.do?menu_idx=116&manage_idx=15&board_idx=<실제 ID>` 형태를 사용한다. 문자열 예시의 ID를 최신 공고로 간주하지 않는다.

## QR만으로 행동 경로를 끝내지 않는다

자기 휴대전화로 SNS를 보는 사람은 같은 화면의 QR을 바로 카메라로 스캔하기 어렵다. 카드에는 `포항TP 홈페이지 → 알림마당 → 사업공고 → [짧은 공고명]`을 함께 쓴다. 사용자가 이미지를 저장해 갤러리 QR 인식 기능을 쓸 수도 있지만 모든 기기에서 지원한다고 단정하지 않는다.

- **Instagram:** 정확한 공고명과 홈페이지 이동 경로를 캡션에 병기한다. 계정 프로필에 실제 해당 링크가 있고 직접 확인했을 때만 `프로필 링크`라고 쓴다. 링크 스티커는 스토리 게시가 별도 요청되었을 때 사용한다.
- **Facebook:** 캡션에 같은 공식 상세 URL을 클릭 가능한 직접 링크로 함께 넣는다.
- **대체텍스트:** 장의 핵심 정보, QR의 목적, 홈페이지 이동 경로를 설명한다. URL만 길게 반복하거나 `QR을 찍으세요`만 쓰지 않는다.
- QR은 문의전화·마감일·신청자격을 대신하지 않는다. 작은 QR을 모든 장에 반복해 시선을 분산시키지 않는다.

## 테오·피오와 배치

테오는 옆에서 QR과 상세 공고의 관계를 설명하고, 피오는 신청 준비 체크리스트나 마감 확인으로 행동을 돕는다. 예: `테오: 자격과 제출서류는 여기서 정확히!` / `피오: 마감 시간도 체크 완료!` 대사도 해당 공고에 맞게 검수한다.

캐릭터 손끝·말풍선·소품·테두리·로고는 **QR 및 주위 4모듈 흰 여백 밖**에 배치한다. QR 중앙에 캐릭터·기관로고를 넣거나 모듈을 둥글게 꾸미지 않는다. 도형 자체는 흑백 고대비, 평면 정면, 불투명 흰 배경을 유지한다. 그림 속 간판·책·모니터에 원근 변형된 QR을 넣지 않는다.

공식 공고 URL과 실제 QR 목적지를 분리해 기록한다. 단축주소가 요청된 경우 아래 단축주소 절차에서 최종 목적지를 확인한 뒤 QR을 생성한다. `generation_method=whole-image`에서는 이 정확한 QR 이미지를 생성 참조로 제공하고, 평면·흑백·4모듈 여백과 충분한 크기를 유지하도록 요청한다. 생성 도구가 패턴을 보존했다고 가정하지 않으며 **최종 이미지의 원본·0.5배에서 독립 디코더가 기대 URL을 읽는 경우만 통과**시킨다. 실패하면 생성 도구로 QR 참조와 보존 조건을 다시 주어 수정·재생성한다. 사용자가 QR 영역만 별도 교체하도록 명시한 작업에는 원본을 보존하고 QR 영역만 정확한 코드로 교체할 수 있다. 2026-10-30 사용자는 지정된 7건(7997, 7681, 7938, 7923, 7814, 7996, 7904)에 이 방식을 허용했다. 그 밖의 작업에 이 허용을 자동 확대하지 않는다. 영역 외 픽셀 동일성을 검사한다. 별도 조판 방식에서는 QR을 분리된 마지막 레이어로 조립하고 최종 래스터 파일에서 같은 검사를 한다. 출처 없는 QR처럼 보이는 무늬를 유효한 코드로 취급하지 않는다.

## 생성과 검증 도구

`scripts/generate_social_qr.py`는 외부 요청 없이 PNG·SVG·생성 JSON을 만들고, `qrcode` 인코더와 별개의 **ZXing-C++**로 PNG를 실제 디코딩한다. 기본값은 오류정정 M, 흑백, 4모듈 여백, 모듈당 8픽셀이다. QR 크기는 URL 길이에 따라 달라진다. 픽셀 단위 원본 크기를 유지하거나 정수 모듈 배율로 배치한다. 단순히 200픽셀 사각형에 맞추지 말고 최종 이미지의 0.5배 축소에서도 읽히는지 확인한다.

격리된 Python 환경을 사용한다. 다음 버전은 Windows Python 3.13에서 생성·독립 디코딩을 확인한 고정 조합이며, 시스템 Python이나 다른 작업의 라이브러리를 변경하지 않는다.

```powershell
python -m venv work/ptp-qr/.venv
& work/ptp-qr/.venv/Scripts/python.exe -m pip install 'qrcode[pil]==8.2' 'Pillow==11.3.0' 'zxing-cpp==2.3.0'

# --output-dir는 아직 존재하지 않는 새 폴더여야 한다.
& work/ptp-qr/.venv/Scripts/python.exe scripts/generate_social_qr.py generate --url $verifiedNoticeUrl --output-dir work/ptp-qr/notice-assets

# 이미지 조립/내보내기 후 전체 카드 이미지를 읽어 URL의 완전 일치를 검사한다.
& work/ptp-qr/.venv/Scripts/python.exe scripts/generate_social_qr.py verify --image $finalCardPath --expected-url $verifiedNoticeUrl --report work/ptp-qr/final-card-qr-report.json --scales 1 0.5
```

스크립트 경로는 실제 스킬 루트에 맞춰 사용한다. 위 변수는 검증된 공고 URL과 실제 최종 PNG 경로를 넣은 셸 변수다. QR 생성용 `qr.png`, `qr.svg`, `qr-report.json`만 자동 작성하며 캐릭터 카드나 문안은 이 도구에서 생성하지 않는다. 파일·폴더를 덮어쓰지 않는다. 기본 허용 호스트는 `ptp.or.kr`, `www.ptp.or.kr`이다. 다른 공공 사이트를 사용해야 한다면 실제 공개 목적지를 먼저 확인한 뒤 `--allow-host 정확한호스트`를 명시한다. 호스트 허용은 내용이나 공개성에 대한 검증을 대신하지 않는다.

## 게시 전 통과 조건

1. QR에 인코딩한 URL과 최종 이미지에서 **독립 디코더가 읽은 URL**이 완전히 일치하며, 단축주소를 쓰면 게시 직전 정확한 공식 공고 URL로의 연결도 재확인한다.
2. 최종 전체 카드의 원본 크기와 0.5배 축소에서 모두 QR 1개가 읽힌다. 실패하면 QR을 키우고 여백/대비/가림을 수정해 다시 내보낸다. 이전의 QR 원본 PNG 검사로 새 최종 카드의 검사를 갈음하지 않는다.
3. 최종 미리보기에서 캐릭터·대사·레이아웃이 여백을 침범하지 않고, 라벨·대체 경로·출처가 읽힌다.
4. 생성 보고서와 최종 파일 디코딩 보고서를 납품 기록에 연결한다. 이미지 SHA-256과 도구 버전을 기록한다. `passed=false`이거나 디코더가 없으면 QR 검증 완료로 표기하지 않는다.
5. 게시 후 플랫폼에서 재압축된 실제 이미지를 받을 수 있으면 별도 파일로 내려받아 다시 검증한다. 이 추가 검증을 하지 않았으면 `플랫폼 재압축본/실물 휴대전화 스캔은 미검증`으로 구분한다. 로컬 PNG 디코딩 통과를 모든 기기에서의 성공으로 표현하지 않는다.

생성 PNG 검사는 SVG 렌더러·카드 조립·플랫폼 압축 검사가 아니다. 검증 도구는 원본/축소 픽셀을 별개로 디코딩하며 예상 URL 이외의 코드가 섞인 이미지도 실패 처리한다. 다른 코드의 평문은 보고서에 저장하지 않는다.

라이브러리 근거: [qrcode 8.2 공식 배포·사용법](https://pypi.org/project/qrcode/8.2/), [ZXing-C++ 2.3.0 Python 바인딩](https://pypi.org/project/zxing-cpp/2.3.0/).

## 무료 단축주소와 대체 경로

저장된 단축주소 기본값 또는 명시적 요청에 따라 `scripts/shorten_notice_url.py`를 사용한다. 기본은 da.gd, 대안은 is.gd다. 기존에 검증한 단축주소가 있으면 재사용하고 매번 새 링크를 발급하지 않는다. 첫 정상 주소가 검증되면 추가 주소를 발급하지 않는다. is.gd 제한·보안 확인이 있으면 우회하지 않는다. TinyURL의 구식 경로는 광고·미리보기 화면 가능성이 있어 기본 대안에서 제외한다. 단축 서비스 전체가 실패하면 실제 실패 보고서와 `fallback_reason`을 기록하고 원문 QR을 사용했음을 알린다. 크기·해독 조건을 충족하지 못하면 게시하지 않는다.

```powershell
python scripts/shorten_notice_url.py --url $verifiedNoticeUrl --report work/ptp-short-links.json
python scripts/shorten_notice_url.py --purpose institution --url $verifiedInstitutionUrl --report work/ptp-institution-short-links.json
python scripts/generate_social_qr.py generate --url $verifiedShortUrl --allow-host da.gd --output-dir work/ptp-short-qr
python scripts/generate_social_qr.py verify --image $finalCard --expected-url $verifiedShortUrl --allow-host da.gd --report work/ptp-final-qr.json --scales 1 0.5 0.321
```

- 기본 모드는 정확한 PTP 사업공고 URL만 받는다. `--purpose institution`은 공개 `html.do?menu_idx=...`와 직원안내 주소도 허용하며 로그인·비밀값·임의 쿼리는 허용하지 않는다. 짧은 링크의 HTTPS Location이 원문 URL과 완전히 일치해야 사용하며 발급·실패·시각·서비스·목적지를 보존한다. 스크립트 확인은 브라우저 접근성과 장기 유지 보장을 뜻하지 않는다.
- 게시 직전 짧은 주소의 연결과 원문의 현재 접수상태를 재확인한다. 발급 후 고장난 단축주소는 다른 단축주소로 새 QR을 만들어 다시 검수한다. 이미 배포된 QR은 자동으로 대안 주소로 바뀌지 않으므로 공개 글을 확인하고 별도 수정 여부를 판단한다.
- HTTP 리디렉션 검사와 실제 브라우저 동작을 구분한다. 2026-10-30 da.gd 신규 주소는 HTTP302 검사에 통과했지만 실제 브라우저에서는 새 주소 확인 화면을 표시했다. 이 경우 표시된 공식 목적지와 클릭 후 본문을 확인하고 해당 동작을 기록한다. 처음부터 즉시 연결된다고 주장하지 않는다. 원래 홈페이지 이동 경로를 함께 유지하며 사용자에게 확인 화면 가능성을 알린다.
- 모바일에서도 이용할 수 있게 캡션에 정확한 공고명과 포항TP 홈페이지 경로를 남긴다. 실제 신청은 공고의 신청 경로로 안내한다. 서비스에 공고 URL이 전달되며 무료 서비스의 유지나 무광고를 보장하지 않는다.
- 공식 근거: https://da.gd/help , https://www.is.gd/apishorteningreference.php , https://tinyurl.com/blog/why-my-tinyurl-link-show-ad-preview-screen-before-redirecting/
