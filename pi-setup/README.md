# Raspberry Pi 키오스크 설정

## 전제 조건

- Raspberry Pi OS 64-bit (Bookworm 이상)
- Python 3.11 이상
- Chromium 브라우저
- USB 열전사 프린터 연결

## 설정 순서

1. `kiosk.sh` 의 `FRONTEND_URL` 을 운영 프론트엔드 주소로 바꿉니다.
2. 자동 로그인 후 `kiosk.sh` 가 실행되도록 시작 프로그램에 등록합니다.
3. `print-service` 가상환경을 만들고 의존성을 설치합니다.
4. systemd 서비스 파일을 등록해 부팅 시 자동 실행되게 만듭니다.

## Print Service 설치

```bash
cd ~/campus-copilot/pi-setup/print-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

sudo cp print-service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable print-service
sudo systemctl start print-service
```

## 확인 방법

```bash
curl http://127.0.0.1:6310/health
```

정상 응답:

```json
{"status":"ok"}
```
