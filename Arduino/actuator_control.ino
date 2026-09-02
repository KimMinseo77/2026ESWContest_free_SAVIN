#include <Servo.h>
#include <LedControl.h>

// ==========================================
// 1. 핀 맵 설정 (회로 연결 기준)
// ==========================================
// DC 모터 드라이버 핀
const int pinSpeed = 3;  // PWM (ENA)
const int pinIn1   = 4;  // 제어신호 1 (IN1)
const int pinIn2   = 5;  // 제어신호 2 (IN2)

// 서보모터 핀
const int PIN_LED_SERVO = 9;   // LED 각도 서보
const int PIN_ARM_SERVO = 6;  // 반사판 지지대 Arm 서보 (10번 핀)

// 도트매트릭스 (MAX7219)
const int PIN_DIN = 12;
const int PIN_CLK = 11;
const int PIN_CS  = 10;

Servo ledServo;
Servo armServo;
LedControl lc = LedControl(PIN_DIN, PIN_CLK, PIN_CS, 1);

// ==========================================
// 2. 기본 상태 및 제어 함수
// ==========================================
const int ARM_WALL_POSITION = 0; // 미사용/안전 시 벽면 밀착 각도
int targetLedAngle = 90;
int targetArmAngle = 90;

// 도트매트릭스 점등/소등
void setMatrix(bool state) {
  for (int row = 0; row < 8; row++) {
    lc.setRow(0, row, state ? 0xFF : 0x00);
  }
}

// DC 모터 제어 함수 (IN1, IN2, PWM 적용)
void setDCMotor(int speed) {
  if (speed > 0) {
    digitalWrite(pinIn1, HIGH);
    digitalWrite(pinIn2, LOW);
    analogWrite(pinSpeed, constrain(speed, 0, 255));
  } else {
    digitalWrite(pinIn1, LOW);
    digitalWrite(pinIn2, LOW);
    analogWrite(pinSpeed, 0);
  }
}

// 모든 액추에이터 안전 모드 초기화
void resetToSafeMode() {
  setMatrix(false);
  setDCMotor(0);
  ledServo.write(90);
  armServo.write(ARM_WALL_POSITION);
}

// 딜레이 도중에도 시리얼 명령 감시
bool checkSerialDuringDelay(int ms) {
  for (int i = 0; i < ms; i++) {
    if (Serial.available() > 0) {
      return true;
    }
    delay(1);
  }
  return false;
}

void setup() {
  Serial.begin(9600);

  // DC 모터 핀 출력 설정
  pinMode(pinSpeed, OUTPUT);
  pinMode(pinIn1, OUTPUT);
  pinMode(pinIn2, OUTPUT);

  // 서보모터 연결
  ledServo.attach(PIN_LED_SERVO);
  armServo.attach(PIN_ARM_SERVO);

  // 도트매트릭스 초기화
  lc.shutdown(0, false);
  lc.setIntensity(0, 15);
  lc.clearDisplay(0);

  resetToSafeMode();
}

void loop() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n');
    data.trim();

    // 1. 사람 감지 시 정지 명령
    if (data == "STOP") {
      resetToSafeMode();
      return;
    }

    // 2. 프로토콜 파싱: TARGET,MODE,DIR_X,DIR_Y,SCORE
    int idx1 = data.indexOf(',');
    int idx2 = data.indexOf(',', idx1 + 1);
    int idx3 = data.indexOf(',', idx2 + 1);
    int idx4 = data.indexOf(',', idx3 + 1);

    if (idx1 > 0 && idx2 > 0 && idx3 > 0 && idx4 > 0) {
      String target = data.substring(0, idx1);
      String mode   = data.substring(idx1 + 1, idx2);
      String dirX   = data.substring(idx2 + 1, idx3);
      String dirY   = data.substring(idx3 + 1, idx4);
      int score     = data.substring(idx4 + 1).toInt();

      if (dirX == "L")      { targetLedAngle = 135;  targetArmAngle = 135; }
      else if (dirX == "C") { targetLedAngle = 90;  targetArmAngle = 90; }
      else if (dirX == "R") { targetLedAngle = 45; targetArmAngle = 45; }

      // ==========================================
      // 까마귀 우선 모드
      // ==========================================
      if (target == "CROW") {
        ledServo.write(targetLedAngle);

        if (score <= 30) {
          resetToSafeMode();
        }
        else if (score <= 50) {
          if (mode == "DAY") {
            setMatrix(false);
            setDCMotor(0);
            armServo.write(ARM_WALL_POSITION);
          } else { 
            armServo.write(targetArmAngle);
            setDCMotor(120); // DC 모터 저속 회전
            setMatrix(true);
            if (checkSerialDuringDelay(150)) return;
            setMatrix(false);
            // 야간: LED 점멸 + DC모터 느리게 회전
            armServo.write(targetArmAngle);
            setDCMotor(120);
            setMatrix(true);
            if (checkSerialDuringDelay(80)) return;
            setMatrix(false);
            if (checkSerialDuringDelay(120)) return;
          }
        }
        else if (score <= 70) {
          setMatrix(true);
          armServo.write(targetArmAngle);
          setDCMotor(120); // DC 모터 저속 회전
        }
        else { // DANGER (71점 이상)
          setMatrix(true);
          armServo.write(targetArmAngle);
          setDCMotor(255); // DC 모터 최대 회전
        }
      }

      // ==========================================
      // 고양이 모드
      // ==========================================
      else if (target == "CAT") {
        setDCMotor(0); // 고양이는 DC 모터 정지

        if (score <= 30) {
          resetToSafeMode();
        }
        else if (score <= 50) {
          ledServo.write(targetLedAngle);
          setMatrix(true);
          if (checkSerialDuringDelay(300)) return;
          setMatrix(false);
        }
        else if (score <= 70) {
          if (mode == "DAY") {
            setMatrix(false);
          } else {
            ledServo.write(targetLedAngle - 20);
            setMatrix(true);
            if (checkSerialDuringDelay(150)) return;
            ledServo.write(targetLedAngle + 20);
            setMatrix(false);
            if (checkSerialDuringDelay(150)) return;
            ledServo.write(targetLedAngle);
          }
        }
        else { // DANGER (71점 이상)
          setMatrix(true);
          if (checkSerialDuringDelay(500)) return;
          setMatrix(false);
          if (checkSerialDuringDelay(500)) return;

        }
      }
    }
  }
}