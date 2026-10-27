# TakeWeaver 계획

- 마감: 2026-10-31 01:00 KST (10/30 09:00 PT). 목표 제출: 10/30 22:00 KST.
- 부문: Open Weights Only (+ Most Innovative, Best Overall 자동 심사)
- 제출폼: https://form.typeform.com/to/V1dSQrkS — 공개 레포(라이선스·설치), 2분 이하 데모 URL, #OpenSourceHiggsfield 소셜 포스트 URL, 모델 목록
- 레포는 지금 프라이빗, 제출 전 public 전환 필요

## MVP 범위
- 장면 2개, VLM 구간 제안 + 사람 확인, 재생성 1회

## 10/28 오전 통과 기준 (못 넘으면 카메라 비교 앱으로 전환)
- [ ] 5090 PC에서 ComfyUI + Wan2.2-TI2V-5B 공식 워크플로 생성 성공
- [ ] comfy-api-proxy 경유로 앱에서 생성 호출
- [ ] 생성 → GPU 메모리 반환 → Qwen3-VL 평가 → 재생성 1회, OOM 없이
- [ ] 구간 두 개를 이어 붙인 완성본 1개

## 차별점 (README/데모에서 강조)
필요한 장면이 기존 take로 이미 채워졌는지 먼저 판단하고, 부족한 장면에만 생성 예산을 쓴다.
선행: Circle Take, video-dailies, VideoRepair
