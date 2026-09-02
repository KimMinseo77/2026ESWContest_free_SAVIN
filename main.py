
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import cv2
import time
import math
import random
import pygame
from datetime import datetime
import serial
from ultralytics import YOLO

# 시간확인 ===========================================
from datetime import datetime

# 1. 현재 날짜 및 시간 가져오기
now = datetime.now()

# 2. 원하는 형식으로 포맷팅 (예: 2026-08-16 14:25:30)
current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
current_hour = now.hour

# 3. 주/야간 판별 (06:00 ~ 18:00 주간)
mode = "DAY (주간)" if 6 <= current_hour < 18 else "NIGHT (야간)"

# 4. 결과 출력
print(f"현재 전체 시간 : {current_time_str}")
print(f"주/야간 판별   : {mode}")
# ===================================================

# ==========================================
# 1. 시리얼 및 사운드 시스템 초기화
# ==========================================
SERIAL_PORT = 'COM3'
BAUD_RATE = 9600

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"[INFO] 오렌지보드 시리얼 연결 성공! ({SERIAL_PORT})")
except Exception as e:
    print(f"[WARNING] 오렌지보드 연결 실패 (시뮬레이션 모드): {e}")
    ser = None

# pygame 사운드 초기화
pygame.mixer.init()

last_sound_played_time = 0
SOUND_COOLDOWN = 0.5  # 한 소리가 끝난 뒤 다음 랜덤 소리가 나올 때까지의 대기 시간(초)

CAT_SOUNDS = []
CROW_SOUNDS = []

# 고양이 음원 목록 로드 (.wav)
for i in range(1, 9):
    for prefix in ['dog', 'thu', 'vac']:
        fname = f"{prefix}{i}.wav"
        if os.path.exists(fname):
            CAT_SOUNDS.append((fname, pygame.mixer.Sound(fname)))
        else:
            print(f"[WARNING] 음원 파일 없음: {fname}")

# 까마귀 음원 목록 로드 (.mp3)
for i in range(1, 10):
    fname = f"owl{i}.mp3"
    if os.path.exists(fname):
        CROW_SOUNDS.append((fname, pygame.mixer.Sound(fname)))
    else:
        print(f"[WARNING] 음원 파일 없음: {fname}")

print(f"[INFO] 로드 완료: 고양이 음원 {len(CAT_SOUNDS)}개 / 까마귀 음원 {len(CROW_SOUNDS)}개")


def play_random_sound(target_type, volume=1.0):
    """
    해당 점수대에 머무는 동안, 소리가 끝나면 계속해서 다른 랜덤 음원을 연속 재생
    """
    global last_sound_played_time
    current_t = time.time()

    # 현재 스피커에서 소리가 재생 중이면 끝날 때까지 대기
    if pygame.mixer.get_busy():
        return

    # 이전 소리가 끝난 후 쿨다운 시간이 지났는지 확인
    if current_t - last_sound_played_time < SOUND_COOLDOWN:
        return

    pool = CAT_SOUNDS if target_type == 'cat' else CROW_SOUNDS
    if not pool:
        return

    fname, sound_obj = random.choice(pool)
    sound_obj.set_volume(volume)
    sound_obj.play()
    last_sound_played_time = current_t
    print(f"🔊 [노트북 스피커] 연속 랜덤 재생: '{fname}' (타깃:{target_type}, 볼륨:{int(volume * 100)}%)")


def stop_all_sounds():
    """사람 감지 시 또는 영역 이탈 시 즉시 음소거"""
    global last_sound_played_time
    if pygame.mixer.get_busy():
        pygame.mixer.stop()
    last_sound_played_time = 0


# ==========================================
# 2. 모델 및 상태 제어 변수
# ==========================================
MODEL_PATH = r"C:\Users\dlgus\PycharmProjects\embeded_SW\v3_best.pt"
model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("[ERROR] 카메라 연결 실패!")
    exit()

PX_150CM = 400
PX_100CM = 300
PX_50CM = 250

animal_tracker = {}
last_sent_time = 0
person_active = False

target_active = False
last_target_seen_time = 0

def get_center(box):
    x1, y1, x2, y2 = box
    return (int((x1 + x2) / 2), int((y1 + y2) / 2))


def calculate_distance(p1, p2):
    return int(math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2))


def get_zone(dist):
    if dist is None or dist > PX_150CM:
        return 0
    elif dist <= PX_50CM:
        return 3
    elif dist <= PX_100CM:
        return 2
    else:
        return 1


def get_direction_code(cx, cy):
    dir_y = "U" if cy <= 200 else "D"
    if cx < 213:
        dir_x = "L"
    elif cx < 426:
        dir_x = "C"
    else:
        dir_x = "R"
    return dir_x, dir_y


def get_position_label(cx, cy):
    pos_y = "위(공중)" if cy <= 200 else "아래(바닥)"
    if cx < 213:
        pos_x = "왼쪽"
    elif cx < 426:
        pos_x = "가운데"
    else:
        pos_x = "오른쪽"
    return pos_x, pos_y


def get_day_night_mode():
   current_hour = datetime.now().hour
   return "DAY" if 6 <= current_hour < 18 else "NIGHT"

# def get_day_night_mode():
#     return "DAY"  # 테스트를 위해 무조건 주간으로 고정

# ==========================================
# 3. 메인 감지 및 우선순위 제어 루프
# ==========================================
print("[INFO] 복합 감지 스마트 퇴치 엔진 가동 중... ('q' 키로 종료)")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    current_time = time.time()
    mode = get_day_night_mode()
    results = model.track(frame, imgsz=640, conf=0.5, persist=True, verbose=False)

    trash_bags = []
    current_animals = []
    person_detected = False

    for r in results:
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            continue

        for box in boxes:
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            xyxy = box.xyxy[0].tolist()
            center = get_center(xyxy)

            if cls_id == 0 or label == 'person':
                person_detected = True
            elif cls_id == 3 or label == 'trash_bag':
                trash_bags.append(center)
            elif cls_id in [1, 2] or label in ['cat', 'crow']:
                track_id = int(box.id[0]) if box.id is not None else None
                if track_id is not None:
                    current_animals.append({
                        'id': track_id,
                        'label': label,
                        'center': center,
                        'box': xyxy
                    })

    annotated_frame = results[0].plot()

    # ----------------------------------------------------
    # [우선순위 1] 사람 감지 시 즉시 정지
    # ----------------------------------------------------
    if person_detected:
        if not person_active:
            if ser and ser.is_open:
                ser.write(b"STOP\n")
            stop_all_sounds()
            print("🛑 [사람 감지] 사람 출현으로 모든 엑추에이팅 및 사운드를 즉시 중단합니다. (STOP 전송)")
            person_active = True

    # ----------------------------------------------------
    # [우선순위 2] 동물 위험도 분석 및 우선순위 스케줄링
    # ----------------------------------------------------
    else:
        if person_active:
            print("🟢 [안전 복귀] 사람이 퇴장하여 동물 감시 모드로 복귀합니다.")
            person_active = False

        # 1초 이상 탐지되지 않은 객체만 tracker에서 삭제
        for tid in list(animal_tracker.keys()):
            if current_time - animal_tracker[tid].get('last_seen', current_time) > 1:
                del animal_tracker[tid]

        analyzed_targets = []

        for animal in current_animals:
            a_id = animal['id']
            label = animal['label']
            a_center = animal['center']

            min_dist = None
            nearest_bag = None
            if trash_bags:
                min_dist = float('inf')
                for b_center in trash_bags:
                    dist = calculate_distance(b_center, a_center)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_bag = b_center

            current_zone = get_zone(min_dist)

            if current_zone == 0:
                if a_id in animal_tracker:
                    del animal_tracker[a_id]
                continue

            # 최초 진입
            if a_id not in animal_tracker:
                animal_tracker[a_id] = {
                    'first_seen': current_time,
                    'last_seen': current_time,
                    'label': label,
                    'zone': current_zone,
                    'dist_score': 10,
                    'last_score': -1,
                    'last_sent_time': 0,
                    'last_print_time': 0
                }

            record = animal_tracker[a_id]

            # 현재 프레임에서 이 동물이 인식됐다는 시간 갱신
            record['last_seen'] = current_time

            prev_zone = record['zone']

            # 거리 가감점
            if current_zone > prev_zone:
                record['dist_score'] += (current_zone - prev_zone) * 10
                record['zone'] = current_zone
            elif current_zone < prev_zone:
                record['dist_score'] = max(0, record['dist_score'] - (prev_zone - current_zone) * 20)
                record['first_seen'] = current_time
                record['zone'] = current_zone

            # 시간 점수 계산
            dwell_time = current_time - record['first_seen']
            if dwell_time < 2.0:
                time_score = 0
            elif dwell_time < 3.0:
                time_score = 20
            elif 3.0 <= dwell_time <= 10.0:
                time_score = int(dwell_time - 2.0) * 4 + 20
            else:
                time_score = 52

            base_score = 10 if label == 'crow' else 0
            total_score = base_score + time_score + record['dist_score']

            # 터미널 상태 출력
            if total_score != record['last_score']:
                print(f"  └─> [총점 갱신] ID:{a_id} ({label}) | 체류:{dwell_time:.1f}초 | 거리:{min_dist}px "
                      f"=> 총점: {total_score}점 (기본:{base_score} + 시간:{time_score} + 누적거리:{record['dist_score']})")
                record['last_score'] = total_score

            if total_score >= 50:
                if current_time - record.get('last_print_time', 0) >= 1.0:
                    cx, cy = a_center
                    pos_x, pos_y = get_position_label(cx, cy)
                    print(f"  [위험 위치 감지] ID:{a_id} ({label}) -> 위치: [{pos_y} / {pos_x}] (좌표: X={cx}, Y={cy})")
                    record['last_print_time'] = current_time

            if nearest_bag:
                cv2.line(annotated_frame, a_center, nearest_bag, (0, 0, 255), 2)

            info_text = f"ID:{a_id} {label} | Time:{dwell_time:.1f}s | Score:{total_score}pts"
            bx1, by1, _, _ = map(int, animal['box'])
            cv2.putText(annotated_frame, info_text, (bx1, max(20, by1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)

            analyzed_targets.append({
                'id': a_id,
                'label': label,
                'center': a_center,
                'score': total_score,
                'dwell_time': dwell_time,
                'record': record
            })

        # ----------------------------------------------------
        # 동시 인식 시 다중 타깃 우선순위 중재
        # ----------------------------------------------------
        if analyzed_targets:
            cat_targets = [t for t in analyzed_targets if t['label'] == 'cat']
            crow_targets = [t for t in analyzed_targets if t['label'] == 'crow']

            # 1. 사운드 제어 (주간일 때만 랜덤 사운드 출력)
            if mode == "DAY":
                # 주간 사운드: 고양이 최우선
                if cat_targets:
                    top_cat = max(cat_targets, key=lambda x: x['score'])
                    if 51 <= top_cat['score'] <= 70:
                        play_random_sound('cat', volume=0.7)  # 24개 고양이 소리 중 랜덤
                    elif top_cat['score'] >= 71:
                        play_random_sound('cat', volume=1.0)  # 24개 고양이 소리 중 랜덤 (최대 음량)
                    else:
                        stop_all_sounds()
                elif crow_targets:
                    top_crow = max(crow_targets, key=lambda x: x['score'])
                    if 31 <= top_crow['score'] <= 50:
                        play_random_sound('crow', volume=0.7)  # 9개 부엉이 소리 중 랜덤
                    elif top_crow['score'] >= 71:
                        play_random_sound('crow', volume=1.0)  # 9개 부엉이 소리 중 랜덤 (최대 음량)
                    else:
                        stop_all_sounds()
                else:
                    stop_all_sounds()
            else:
                # 야간: 무음 규정
                stop_all_sounds()

            # 2. 하드웨어(빛/모터) 타깃 선정 (까마귀 최우선)
            selected_target = None
            if crow_targets:
                selected_target = max(crow_targets, key=lambda x: x['score'])
            elif cat_targets:
                selected_target = max(cat_targets, key=lambda x: x['score'])

            # 3. 오렌지보드로 명령 송신 (1초 주기)
            if selected_target:
                target_active = True
                last_target_seen_time = current_time

                rec = selected_target['record']

                if current_time - rec.get('last_sent_time', 0) >= 1.0:
                    dir_x, dir_y = get_direction_code(selected_target['center'][0], selected_target['center'][1])
                    target_name = "CROW" if selected_target['label'] == 'crow' else "CAT"

                    cmd = f"{target_name},{mode},{dir_x},{dir_y},{selected_target['score']}\n"
                    if ser and ser.is_open:
                        ser.write(cmd.encode())

                    print(
                        f"📡 [명령 송신 ({mode})] 타깃:{target_name} | 방향:[{dir_x},{dir_y}] | 점수:{selected_target['score']}점")
                    rec['last_sent_time'] = current_time

        else:
            stop_all_sounds()

            # 직전까지 객체가 있었고,
            # 마지막 탐지 후 1초 이상 지나면 진짜 이탈로 판단
            if target_active and current_time - last_target_seen_time >= 1.0:
                print("⚪ [객체 없음] 감지 대상이 없습니다.")

                if ser and ser.is_open:
                    ser.write(b"STOP\n")

                print("🟢 [액추에이터 초기화] STOP 전송 → 모든 액추에이터 초기화")

                target_active = False

    cv2.imshow("Smart Trash Risk Engine v8", annotated_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

if ser and ser.is_open:
    ser.close()
stop_all_sounds()
cap.release()
cv2.destroyAllWindows()