# FaceTrue Restore 계획

## 한 줄 아이디어
옛날 가족 영상(VHS·8mm, 흑백 가능)과 그 사람의 별도 실제 사진을 넣으면, 내 PC에서 오픈 웨이트로 복원하면서 얼굴이 사진 속 그 사람으로 유지되는 HD 영상이 나온다.

## 대회 정보
- 마감: 2026-10-31 01:00 KST. 목표 제출: 10/30 22:00 KST.
- 노리는 상: Open Weights Only(RTX 5090), LTX VFX 보너스($2,000, LTX가 핵심 모델이어야 함)
- 제출폼: https://form.typeform.com/to/V1dSQrkS
- 레포는 지금 프라이빗. 제출 직전에 public 전환.

## 기능
### MVP
- [ ] 3분할 비교(핵심 차별점): 원본 / 사진 없이 복원 / 사진 넣고 복원, 같은 프레임 기준
- [ ] 얼굴 클릭 + 사진 드롭 → 참조 캔버스 자동 생성(출력 크기 회색 캔버스, 얼굴 위치에 붙임, frame_idx -1)
- [ ] 자동 분할·이어 붙이기(97프레임 창, 17프레임 겹침)
- [ ] 디인터레이스
- [ ] 시대에 맞는 negative prompt 프리셋
- [ ] 와이프 비교 MP4 내보내기
- MVP 제한: 한 사람, 4~10초 클립, 고정 구도 먼저

### 나중에
- [ ] 얼굴이 움직일 때 구간마다 참조 위치 다시 배치(얼굴 추적)
- [ ] 여러 사람, 더 긴 클립
- [ ] 연결부 검토 화면

## 구조
- 5090 PC(32GB): ComfyUI(8188) ← comfy-api-proxy(127.0.0.1:8189) ← comfy-sdk
- 앱: FastAPI + 얇은 웹 UI, FFmpeg/OpenCV(디인터레이스, 분할, 이어 붙이기, 비교 영상)
- 모델: LTX-2.5 22B + Restore IC-LoRA. 카드 설정: 8 steps, CFG 1, 960x544 타일, 97프레임 창 / 17프레임 겹침
- 저VRAM: INT8 transformer + INT8 Gemma + offload, RAM 64GB 이상 권장
- 참조 경로는 use_streaming off 필요

## 10/28 오전 중단 판정 (못 넘으면 접고 OIBC로)
- [ ] 공식 저VRAM 설정으로 49프레임 완주
- [ ] 97프레임 완주
- [ ] 10초 클립 완주(로딩·샘플링·디코드 시간, VRAM/RAM 최고치 기록)
- [ ] 인위적으로 열화한 클립 3개에서 무참조 / 올바른 참조 / 다른 사람 참조를 같은 seed로 비교
- [ ] 올바른 참조가 무참조보다 일관되게 더 닮음
- 계속 조건: 올바른 참조가 일관되게 더 닮고, 최소 한 파일이 끝까지 나와야 함. 아니면 중단.

## 일정 (KST)
- 10/28 오전: 중단 판정 테스트
- 10/28 오후: 참조 캔버스 생성, 분할·이어 붙이기 파이프라인
- 10/29: 3분할 비교 UI, 디인터레이스, 프리셋, 와이프 MP4 내보내기
- 10/30 낮: 데모 영상(2분 이하), README 설치법, 소셜 포스트
- 10/30 22:00: 제출

## 데모
- 첫 10초: 실제 사진 옆에 사진 없는 복원과 사진 넣은 복원을 나란히
- 소스: 퍼블릭 도메인 Prelinger 홈무비 등
  (예: https://commons.wikimedia.org/wiki/File:Home_Movies_-_Western_U.S.,_New_Mexico,_Mexico,_California,_Colorado,_Utah.webm)
- 참조는 반드시 별도 사진. 복원 대상 프레임 자체를 참조로 쓰지 않음.
- 인위적으로 열화한 테스트 클립은 화면에 표시

## 제출 체크리스트
- [ ] README 설치법·라이선스·모델 목록 완성
- [ ] 레포 public 전환
- [ ] 2분 이하 데모 영상 URL
- [ ] #OpenSourceHiggsfield 소셜 포스트 URL
- [ ] 모델 목록 기입(LTX-2.5 22B, Restore IC-LoRA, Gemma 인코더)
- [ ] Typeform 제출

## 위험과 솔직한 위치
- 비슷한 연구가 이미 있음: IP-FVR, RG-FVR(참조 사진 기반 얼굴 영상 복원)
- Topaz Image에는 참조 사진 얼굴 복원 기능이 이미 있음(Topaz Video는 미확인)
- LTX Restore HF Space가 이미 있음: winterwarrior/ltx-restore-demo, breslavsky/ltx-restore-studio
- 사진이 실제로 닮음을 개선하지 않을 수 있음 → 10/28 판정으로 확인
- 32GB에서 렌더 시간 미측정
- 참조 + 긴 클립 연결이 충돌할 수 있음
- 복원은 생성 방식이라 색·세부는 복구가 아니라 재구성
- 주장하지 않을 것: "길이 제한 없음", "Veo/Sora는 아이 영상을 거부" (Sora 제품은 2026-04-26 종료)
- 내세울 것: 원본 / 무참조 / 참조 복원을 직접 비교해 사진의 효과를 보여 주는 로컬 오픈 웨이트 앱
