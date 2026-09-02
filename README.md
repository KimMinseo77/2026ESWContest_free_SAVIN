# SAVIN — AI 기반 스마트 쓰레기 집하장 관리 시스템

야생동물(까마귀·고양이)의 도심 쓰레기 집하장 접근을 온디바이스 AI로 실시간 탐지하고,
동물에게 상해를 입히지 않는 비접촉 방식(서보 조준·주야간 차등 자극·종별 맞춤 음원)으로
쓰레기 훼손을 방지하는 시스템입니다. (2026년 임베디드 소프트웨어 경진대회 출품작)

## 개발 배경 및 목표

- 도심 야생동물의 쓰레기 접근으로 인한 봉투 파손·부상 위험·반복 민원 문제 해결
- 단순 포획·퇴치가 아닌, **동물을 해치지 않고 쓰레기 접근만 통제**하는 관리 시스템 제안
- On-device AI 기반 실시간 객체 탐지 + 상황 맞춤형 단계별 액추에이팅 + 주야간 안정성 확보

## 시스템 구성

```
카메라 → 영상 입력/처리 → 객체 탐지·추적(YOLOv8n) → 위험도 분석(거리·체류시간) 
       → 퇴치 제어 결정(동물 종류·위험 점수) → 음향 출력 / 시리얼 통신 
       → 액추에이터 제어(Orange Board: LED·반사판 서보, DC모터, 도트매트릭스)
```

- **Host PC / Edge Board**: 카메라 영상 획득, YOLO 실시간 객체 탐지, 위험 점수 산출, 제어 명령 전송
- **Orange Board (MCU)**: 시리얼 명령 수신·파싱, 액추에이터(서보·모터·LED·매트릭스) 실시간 제어

## 저장소 구조

```
Project/
├── main.py                        # 메인 실행 파일 (영상 입력, YOLO 탐지·추적, 위험도 판단, 시리얼 전송 통합)
├── model/
│   ├── v3_best.pt                 # YOLOv8n 학습 완료 가중치 (PyTorch)
│   ├── v3_best.onnx                # ONNX 변환 모델 (FP32)
│   └── v3_best_int8.onnx           # ONNX INT8 양자화 모델
├── Arduino/
│   └── actuator_control.ino        # Orange Board 펌웨어 (시리얼 수신 + 액추에이터 제어)
├── sound/                          # 동물 종류별 퇴치 음원
│   ├── cat/                        # 고양이 대응: dog(개 짖는 소리), thunder(천둥), vacuum(청소기)
│   └── crow/                       # 까마귀 대응: owl(부엉이 울음)
├── dataset/                        # 학습 데이터셋 설정
│   ├── data.yaml                   # 클래스 정보(4종) 및 상대경로 설정
│   ├── labels.zip                  # 라벨(YOLO txt) 압축 파일 — 이미지 원본은 용량 문제로 미포함 (보관처는 팀 내 별도 공유)
│   └── v3-model-code.ipynb             # YOLOv8n 모델 학습 및 성능 검증 코드 (Kaggle Notebook, Tesla T4)
└── verification/                   # PC/보드 실측 검증
    ├── pc/                         # 노트북(PC, CPU) 환경 검증
    │   ├── pc_convert_and_eval.py  # .pt → .onnx(FP32) → .onnx(INT8) 변환 및 mAP·속도 측정
    │   └── results.csv             # 포맷별 mAP(전체·클래스별)·추론속도 측정 결과
    └── board/                      # 임베디드 보드(Jetson Xavier NX) 환경 검증
        ├── convert_and_benchmark_fp16.sh   # .onnx → TensorRT(FP16) 엔진 변환 + 속도 벤치마크
        └── board_benchmark_log.txt         # 보드 실측 속도 로그 (trtexec 결과)
```

## 개발 환경

### PC (SW 개발 / AI)
| 구분 | 내용 |
|---|---|
| OS | Windows 11 |
| IDE | PyCharm |
| AI Framework | Ultralytics YOLOv8 |
| 통신 | PySerial |
| 사운드 | Pygame |

### 모델 학습
| 구분 | 내용 |
|---|---|
| 모델 | YOLOv8n |
| 학습 환경 | Kaggle Notebook (NVIDIA Tesla T4) |
| 데이터 | 4-Class (person, cat, crow, trash_bag) |

### Firmware
| 구분 | 내용 |
|---|---|
| 개발 도구 | Arduino IDE |
| 언어 | Arduino C/C++ |
| 대상 보드 | Orange Board |

### 검증 (verification/)
| 구분 | PC | 보드 |
|---|---|---|
| 하드웨어 | Intel Core Ultra X7 358H (CPU only) | 한백전자 AI Mavin (NVIDIA Jetson Xavier NX) |
| 추론 엔진 | ONNX Runtime | TensorRT 7.1 |
| 역할 | 포맷별(.pt/.onnx-fp32/.onnx-int8) mAP·속도 측정 | TensorRT FP16 엔진 변환 및 실측 속도 벤치마크 |

## 실행 방법

### 1. 메인 시스템 실행 (PC)
```bash
pip install ultralytics opencv-python pyserial pygame
python main.py
```
> `main.py` 내 `SERIAL_PORT = 'COM3'` 값을 실제 Orange Board가 연결된 포트로 수정필요.

### 2. Orange Board 펌웨어 업로드
Arduino IDE에서 `Arduino/actuator_control.ino` 열고 보드에 업로드
(필요 라이브러리: `Servo.h`, `LedControl.h`)

### 3. 검증 스크립트 실행

**PC:**
```bash
cd verification/pc
python pc_convert_and_eval.py --weights ../../model/v3_best.pt --data ../../dataset/data.yaml
```

**보드 (Jetson):**
```bash
cd verification/board
chmod +x convert_and_benchmark_fp16.sh   # 최초 1회, 실행 권한 부여
./convert_and_benchmark_fp16.sh model_fp32.onnx
```

## 주요 검증 결과 요약

| 환경 | 포맷 | mAP50 | 평균 추론시간 |
|---|---|---|---|
| PC (CPU) | pt (원본) | 82.26% | 30.24 ms |
| PC (CPU) | onnx-fp32 | 81.53% | 98.50 ms |
| PC (CPU) | onnx-int8 | 79.91% | 165.98 ms |
| **보드 (Jetson)** | **TensorRT FP16** | – | **11.35 ms (약 88 FPS)** |

→ 저가형 임베디드 보드에서도 노트북 대비 최대 14.6배 빠른 실시간 추론(약 88FPS) 확보

## 데이터셋 안내

`dataset/labels.zip`에는 라벨(YOLO txt)만 포함되어 있으며, 원본 이미지는 용량 문제로
저장소에 포함하지 않았습니다. 학습을 처음부터 재현하려면 이미지 데이터를 별도로 준비한 뒤,
`dataset/data.yaml`이 있는 위치를 데이터셋 루트로 두고 `images/train`, `images/val`, `images/test`
폴더를 그 안에 구성하세요.

## 알려진 이슈 (TODO)

- [ ] 온보드 mAP 정밀 측정 (현재 보드 구형 TensorRT 7.1 호환성 문제로 속도만 실측, 정확도는 후속 검증 예정)

## 참고문헌

[1] 연합뉴스, 「사람 공격하고 쓰레기봉투 파헤치고…창원서 큰부리까마귀 골치」, 2026.06.12.
[2] 연합뉴스, 「창원시, 농업기술센터 청사에도 길고양이 공공급식소 설치」, 2024.03.15.
[3] D. Menaga, Roshan P M, Sangamithra M, "SafeBin: Waste Monitoring and Sharp Object Detection for Animal Welfare Using YOLO Based Vision," 2026 International Conference on Connected Intelligence for Industrial Applications (CI2A), 2026.04.03.
