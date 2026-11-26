# 짧은 영상·릴스 제작

먼저 출력 지면·목적·길이, 사실 출처, 캐릭터 세트, 게시 범위를 확정한다. 세로 릴스는 1080×1920, 정사각 영상은 1080×1080, 30fps를 제작 시작값으로 쓰고 실제 계정의 업로드·미리보기 조건을 확인한다. 사업공고를 다루면 공고 ID, 원문·첨부·신청기간 및 중복 확인 절차를 적용한다.

## 콘티와 조립

1. 독자가 알아야 할 사실과 행동을 정하고 도입→전개→결과를 장면표에 배분한다. 장면별 시작·종료, 화면 행동·구도·자막·내레이션·출처를 기록한다. 반복 인물은 선택한 캐릭터 앵커를 사용한다. 웹툰에서 영상화할 때는 장면의 행동과 전환을 설계하고 핵심 정보가 화면에 충분히 오래 보이게 한다.
2. 원화·프레임은 현재 세션의 이미지 생성이나 로컬 합성 도구를 사용한다. PNG 프레임을 쓰면 새 프레임 폴더에 0부터 연속된 6자리 파일명(`000000.png`)으로 저장한다. 기존 애니메이션 GIF는 직접 입력할 수 있다. 자막·효과음을 컷 전환 및 대사에 맞춘다.
3. 한국어 음성이 필요하면 사용 환경에 설치된 Supertonic 3의 Python으로 문장별 WAV를 합성한다. Windows에서는 기본 Codex 설치 경로를 현재 직원 계정 기준으로 찾는다. 다른 위치에 설치했으면 해당 Python 경로를 사용한다.

```powershell
$ttsPython = Join-Path $env:USERPROFILE '.codex/skill-envs/supertonic-3/Scripts/python.exe'
& $ttsPython -X utf8 -m supertonic.cli tts '포항테크노파크 지원사업을 만나 보세요.' --model supertonic-3 --voice M1 --lang ko --steps 10 --speed 1.02 -o 'line-01.wav'
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 line-01.wav
```

발화가 지정되면 해당 화자·음원을 우선한다. 실제 WAV 길이를 자막과 대조하고 구간이 짧으면 대사 또는 컷 길이를 조정한다. 설치된 음성 환경이나 음원이 필요하지만 없는 경우에는 완성 가능한 콘티·무음 미리보기를 보존한다. 음성을 포함하라는 요청은 실제 음원과 최종 검수를 마쳐야 완료한다.

4. `ffmpeg`와 `ffprobe`가 PATH에 있는 환경에서 작업 폴더에 `edit.json`을 만든다. 파일 경로는 JSON 기준이다. 예시는 4초·120프레임이다. 음성 시작과 종료는 실제 WAV 길이에 맞게 바꾼다.

```json
{
  "duration": 4,
  "fps": 30,
  "size": [1080, 1920],
  "visual": {"type": "frames", "path": "frames"},
  "captions": [{"id": "intro", "start": 0.2, "end": 3.8, "text": "포항테크노파크 지원사업을 만나 보세요."}],
  "audio": [{"role": "voice", "file": "line-01.wav", "start": 0.25, "caption_id": "intro"}]
}
```

GIF는 `visual={"type":"gif","path":"motion.gif","mode":"hold"}`로 바꾼다. `loop`를 선택하면 반복한다. 이어 붙인 장면 클립을 새 음성·자막과 조립하려면 `visual={"type":"video","path":"shots.mp4"}`로 지정한다. 이 입력은 영상 트랙을 사용하며 보존할 음성은 별도의 WAV로 `audio`에 넣는다. 무음은 `audio: []`로 둔다. 자막에는 FFmpeg의 `subtitles` 필터와 한글 표시가 가능한 글꼴이 필요하다. 필요하면 `caption_font`로 설치 글꼴을 지정한다.

```powershell
python -X utf8 scripts/assemble_video.py '작업폴더/edit.json' --output '작업폴더/final.mp4'
```

## 검수와 게시

- 최종 MP4를 처음부터 끝까지 확인하고 스마트폰 미리보기에서 화면 잘림, 읽기 시간, 자막·발화 일치, 오디오 레벨, 처음과 끝, 캐릭터·브랜드·사실·권리를 확인한다. QR을 쓰면 최종 MP4에서 추출한 노출 프레임을 실제 해독하고 읽을 시간을 확인한다. Supertonic을 쓴 공개 영상은 캡션에 실제 모델과 화자를 표시한다. 기본 화자 예시는 `AI 합성 내레이션(Supertonic 3 M1)`이다.
- 작업 폴더에 검수한 채널용 MP4, 영상에서 추출한 PNG 표지, 콘티·채널별 캡션·영상 검수 기록을 보존한다. 영상 검수 기록에는 규격·길이·음성/자막 검수와 실제 영상 SHA-256을 남긴다. 기존 이미지 검수 계약에 표지·필요한 프레임을 실제 파일로 연결하고, 패키지 manifest의 `files[]`에는 영상·표지·검수·캡션의 파일 길이와 SHA-256을 기록한다. 공고 영상은 [원문 접수기간과 게시 게이트](notice-to-social-workflow.md#4-검수-후-게시-또는-납품)도 적용한다. 기존 회차에 지정된 캐러셀 형식 및 채널 게이트는 원래 편성을 따른다.
- 확정된 게시 범위와 [채널별 계정·중복 검사](social-publishing.md)를 적용한다. 실제 업로드는 MP4만 사용하고, 표지는 지원되는 별도 표지 입력에 사용한다. 업로드 직전에 게시할 MP4 해시를 검수 기록과 다시 대조한다. 요청 지면과 실제 게시 미리보기에서 영상·표지·캡션·공개 범위를 확인하고 채널별 `submitting` 이후 한 번 제출한다. 공개 주소를 열어 실제 영상·캡션과 재생 상태를 확인한다.
