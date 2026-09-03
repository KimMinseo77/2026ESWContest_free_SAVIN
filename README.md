# SAVIN — AI 기반 스마트 쓰레기 집하장 관리 시스템

야생동물(까마귀·고양이)의 도심 쓰레기 집하장 접근을 온디바이스 AI로 실시간 탐지하고,
동물에게 상해를 입히지 않는 비접촉 방식(서보 조준·주야간 차등 자극·종별 맞춤 음원)으로
쓰레기 훼손을 방지하는 시스템

## 개발 배경 및 목표

- 도심 야생동물의 쓰레기 접근으로 인한 봉투 파손·부상 위험·반복 민원 문제 해결
- 단순 포획·퇴치가 아닌, **동물을 해치지 않고 쓰레기 접근만 통제하는 관리 시스템** 제안
- On-device AI 기반 실시간 객체 탐지 + 상황 맞춤형 단계별 액추에이팅 + 주야간 안정성 확보

## 시스템 구성

```
카메라 → 영상 입력/처리 → 객체 탐지·추적(YOLOv8n) → 위험도 분석(거리·체류시간) 
       → 퇴치 제어 결정(동물 종류·위험 점수) → 음향 출력 / 시리얼 통신 
       → 액추에이터 제어(Orange Board: LED·반사판 서보, DC모터, 도트매트릭스)
```

- **Host PC / Edge Board**: 카메라 영상 획득, YOLO 실시간 객체 탐지, 위험 점수 산출, 제어 명령 전송
- **Orange Board (MCU)**: 시리얼 명령 수신·파싱, 액추에이터(서보·모터·LED·매트릭스) 실시간 제어

## 위험 점수 산출 로직

> **위험 점수 = 동물 종류 + 체류시간 + 접근 거리** 기반으로 산출되며,
> **쓰레기봉투에서 멀어질수록 -20점 감점**되어 실제 위협이 아닌 단순 통과는 낮은 점수로 처리됩니다.
>까마귀의 경우는 기본점수 10점을 추가합니다.

산출된 최종 위험 점수에 따라 시스템 동작을 4단계로 구분하며 동물 종류·주야간에 따라 서로 다른 액추에이터 조합으로 대응합니다.

| 위험 단계 | 점수 범위 | 동작 |
|---|---:|---|
| SAFE | 0~30점 | 안전 상태 유지 |
| MONITORING | 31~50점 | 객체 위치 추적 및 저강도 대응 |
| WARNING | 51~70점 | 중강도 퇴치 자극 |
| DANGER | 71점 이상 | 고강도 퇴치 자극 |

(야간 모드는 도트매트릭스 점등·점멸과 반사판 회전 위주로 시각 자극을 강화)

사람이 감지된 경우 위험 점수와 관계없이 퇴치 동작을 중단하고
Orange Board에 `STOP` 명령을 전송하여 액추에이터를 안전 상태로 전환합니다.

## 파일 구조

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
│   ├── labels.zip                  # 라벨(YOLO txt) 압축 파일 — 이미지 원본은 용량 문제로 미포함
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
> `main.py` 내 `SERIAL_PORT = 'COM3'` 값을 실제 Orange Board가 연결된 포트로 수정 필요.

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

전체 학습 데이터셋은 저장소 용량을 고려하여 포함하지 않았으며,
데이터셋의 구성 및 YOLO 라벨 형식을 확인할 수 있도록 일부 샘플 데이터를 제공.

`dataset_sample/`에는 실제 학습에 사용한 데이터 중 일부 이미지와
각 이미지에 대응하는 YOLO 형식의 라벨(`.txt`)이 포함.

```text
dataset_sample/
├── images/
│   ├── train/
│   ├── val/
│   └── test/
├── labels/
│   ├── train/
│   ├── val/
│   └── test/
└── data.yaml
```

샘플은 person, cat, crow, trash_bag의 4개 클래스로 구성되어 있으며,
원본 데이터셋의 Train / Validation / Test 분할 구조를 유지.

※ 전체 학습 데이터셋이 아닌 구조 확인용 샘플이므로,
본 저장소의 샘플 데이터만으로 최종 모델의 학습 결과를 동일하게 재현할 수는 없음.

## 실험 한계점 및 향후 개선

- 사용한 보드의 JetPack 4.4 및 TensorRT 7.1 환경에서 최신 Ultralytics 기반 ONNX 모델을 변환·추론하는 과정에서 그래프 호환성 문제가 발생하였으며, Bounding Box의 `w`, `h` 값이 비정상적으로 산출되는 현상을 확인.

- 동일한 ONNX 모델을 PC의 **ONNX Runtime 환경에서 실행했을 때는 정상적인 객체 탐지 결과를 확인.**
  이에 따라 해당 현상은 학습된 모델 자체보다는 **구형 JetPack/TensorRT 환경과 ONNX 모델 간의 호환성 문제**로 판단.

- 따라서 본 프로젝트에서는 최종 시연의 안정성을 위해 **노트북에서 객체 탐지 및 판단을 수행하고, Orange Board를 통해 액추에이터를 제어하는 방식**으로 시스템을 구성.

- 향후에는 **최신 JetPack을 지원하는 임베디드 보드 환경에서 모델을 재검증**하거나, 해당 TensorRT 버전과 호환되는 ONNX 변환 설정을 적용하여 온보드 추론 및 정확도 평가를 추가로 수행할 예정.

## 참고문헌

[1] 연합뉴스, 「사람 공격하고 쓰레기봉투 파헤치고…창원서 큰부리까마귀 골치」, 2026.06.12.
[2] 연합뉴스, 「창원시, 농업기술센터 청사에도 길고양이 공공급식소 설치」, 2024.03.15.
[3] D. Menaga, Roshan P M, Sangamithra M, "SafeBin: Waste Monitoring and Sharp Object Detection for Animal Welfare Using YOLO Based Vision," 2026 International Conference on Connected Intelligence for Industrial Applications (CI2A), 2026.04.03.
[4] Applied Animal Behaviour Science, "Veterinary background noise elicits fear responses in cats while freely moving in a confined space and during an examination," 2022.
[5] T. G. Jalgaonkar et al., “Emerging technology-driven bird deterrence methods for agricultural crop protection: a systematic literature review,” Smart Agricultural Technology, Vol. 14, 2026, 102403.
