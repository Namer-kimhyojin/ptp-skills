# 캐릭터 세트 선택·등록

## 호출과 선택

- “캐릭터 없이 단일 포스터” → `none`.
- “테오·피오로 카드뉴스” → `teo-pio`.
- “테오만 설명하는 카드뉴스” → `teo`.
- “피오 단독으로 홍보” → `pio`.
- “저장한 ○○ 세트로 제작” → 목록에서 ID·이름·별칭을 정확히 확인한다. 없거나 모호하면 비슷한 세트로 자동 대체하지 않는다.

새 제작에서 캐릭터가 미지정이면 “캐릭터 없이 / 테오·피오 / 테오만 / 피오만 / 추가 등록 세트” 중 사용 가능한 목록을 제시한다. 이미 선택했거나 기존 작업·연재에 지정된 경우 다시 묻지 않는다. 콘텐츠 형식과 캐릭터 선택은 독립적이다. 캐릭터 없음도 단일 이미지·카드뉴스·사물과 내레이션 중심 웹툰에 사용할 수 있다. 무인 실행과 선택 위임의 기존 기본값은 테오·피오다. 기존 연재의 캐릭터를 임의로 바꾸지 않는다.

```powershell
python scripts/character_sets.py list
python scripts/resolve_context.py --character-set "테오만" --render-style 2d --delivery-form card-news
python scripts/resolve_context.py --character-set none --delivery-form single-image
python scripts/resolve_context.py --character-set teo-pio --content-type social-toon
```

`--character`는 이전 호출 호환용이다. `--character-set`과 서로 다른 출연진을 지정하면 차단한다. 지원하지 않는 스타일·비활성 세트는 대체 없이 오류로 알린다. `draft` 세트는 제작 초안에만 사용하고 게시에서는 차단한다.

## 새 세트 만들고 저장하기

사용자가 새 캐릭터 세트 제작을 요청하면 이름·역할·시각 스타일과 사용할 인원에 맞춰 실제 기준 이미지와 정체성 명세를 만든다. 이미지 생성은 사용 가능한 내장 이미지 생성 도구로 수행한다. 이 기능 추가만 요청한 경우 새 캐릭터 원화를 임의로 제작하지 않는다.

1. 세트별 폴더 `assets/characters/<set-id>/`에 실제 마스터 이미지와 정체성 명세를 보존한다. 명세에는 외형·비율·복장·색·역할·허용 변형·권리 근거를 적는다. 테오·피오 규칙을 다른 세트에 강제하지 않는다.
2. 마스터 이미지를 기존 `assets/asset-manifest.json` 형식에 맞춰 고유 `AST-...` ID, `kind=character-anchor`, 고유 `CHR-...`의 `character_id`, 실제 경로·픽셀 크기·색상·SHA-256·출처·권리/검토 상태로 등록한다. 실제 검토 없이 `approved`를 기록하지 않는다. `validate_assets.py --level standard`로 확인한다. 기존 자산·승인·공유 장부는 보존한다.
3. 아래 세트 JSON을 작성하고 `register`로 목록에 추가한다. 이름·별칭 충돌, 없는 파일, 다른 캐릭터의 앵커, 해시 불일치는 거부된다. `ready`는 승인 앵커만 허용한다. 등록이 새 게시 권한이나 사람의 승인을 만들지는 않는다.

```json
{
  "id": "saved-team-v1",
  "name": "실제 제작한 세트 이름",
  "version": "1.0",
  "status": "draft",
  "aliases": ["사용자가 부를 별칭"],
  "identity_spec": "assets/characters/saved-team-v1/identity.json",
  "references": [],
  "render_styles": ["2d"],
  "members": [
    {
      "id": "CHR-EXAMPLE",
      "name": "실제 캐릭터 이름",
      "role": "설명·질문 등 고유 역할",
      "anchor_ids": ["AST-EXAMPLE-ANCHOR"]
    }
  ]
}
```

위 ID와 경로는 작성 예시이며 설치된 자산이 아니다. 3D 등 추가 기준 파일은 멤버별 `style_assets: {"3d": ["assets/characters/.../style.png"]}`에 연결한다. `render_styles`에는 실제 준비된 스타일만 적는다. 생성 시 사용한 스타일 참조도 기존 자산·권리 검사와 `publication_asset_ids`에 포함한다. `legacy_family`와 `legacy_key`는 기본 테오·피오 전용이다.

```powershell
python scripts/character_sets.py register --file work/new-character-set.json
python scripts/character_sets.py resolve --set saved-team-v1 --render-style 2d
```

`register`는 기존 ID를 덮어쓰지 않는다. 새 개정판은 `saved-team-v2`처럼 새 ID로 등록해 기존 제작물의 선택 기록을 유지한다. `disabled`는 신규 사용을 중단할 때 쓰며 기존 완성 패키지 자체를 고치지 않는다.

## 작업에 적용·검수

```powershell
python scripts/character_sets.py apply --job assets/single-image-job-template.json --set none --evidence "사용자가 캐릭터 없이 제작하도록 요청" --output work/new-job.json
```

`apply`는 새 초안 파일만 쓴다. 확정·납품 작업과 기존 출력 파일은 덮어쓰지 않는다. 선택 스냅샷, 출연진, 앵커, 선택 근거를 기록하고 과거 게시 검토·자산 선언은 제거한다. 각 캐릭터의 행동은 `design.character_integration.actions`에 캐릭터 ID를 키로 작성한다. 템플릿의 `teo_action`·`pio_action`을 다른 세트에 요구하지 않는다.

세트 변경 후 컷·대사·화자·레이어·포즈·캡션·대체텍스트에 남은 이전 캐릭터를 재검수한다. 웹툰 초안 적용 시 컷 출연진을 비우고 `cast_revision_required=true`로 표시하므로 실제 콘티를 다시 작성하고 검수한 뒤 false로 바꾼다. `none`에서는 마스코트·캐릭터 포즈를 생성 참조에서 빼고 빈 캐릭터 레이어도 제거한다. 기본 템플릿에 남은 문자·내러티브가 자동으로 교정됐다고 간주하지 않는다.

`job.character_set`은 ID·버전·정의 해시·멤버 순서·기준 파일 해시를 저장한다. 이 스냅샷을 캐릭터 캐시의 값/의존성 및 최종 manifest에 포함한다. `layer_cache.py --job <job.json>`을 사용하면 작업 파일 변화가 캐시에 반영된다. 세트가 달라지면 이전 세트의 포즈·장면 캐시를 재사용하지 않는다.

기존 세트 필드가 없는 테오·피오 작업은 호환 유지한다. 새 세트가 선택된 작업은 일반·빠른 초안·게시·웹툰 검사에서 선택한 멤버와 기준을 대조한다. 게시 전에는 선택한 세트의 승인 앵커, 실제 사용 자산, 권리와 결과물 검수를 모두 통과해야 한다.
