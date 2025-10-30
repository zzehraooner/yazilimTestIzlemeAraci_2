# Bizim Performans Aracı

Dynatrace benzeri hafif kaplama: herhangi bir komutu CLI üzerinden çalıştırırken CPU / RAM metriklerini toplayıp FastAPI backend'ine gönderir, veriler PostgreSQL'de saklanır ve React frontend üzerinden görselleştirilir.

## Bileşenler

- **Backend** (`backend/`): FastAPI + SQLAlchemy + PostgreSQL + Alembic.
- **CLI** (`cli/`): Python, `subprocess`, `psutil`, `requests`.
- **Frontend** (`frontend/`): React (Vite), Axios, Chart.js.

Portlar: Backend `http://localhost:8000`, Frontend `http://localhost:3000`.

## Başlarken

### Gereksinimler

- Python 3.10+
- Node.js 18+
- PostgreSQL 13+

### Veritabanı

```bash
createdb perf_local
```

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

set DATABASE_URL=postgresql://localhost/perf_local  # Windows (PowerShell: $env:DATABASE_URL=...)
# export DATABASE_URL=postgresql://localhost/perf_local  # macOS/Linux

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # http://localhost:3000
```

### CLI

```bash
cd cli
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

# Opsiyonel: backend URL'si farklıysa
set BIZIM_BACKEND_URL=http://localhost:8000

bizim-performans-araci run "python -c \"import time; [time.sleep(1) for _ in range(10)]\""
```

## API Özeti

- `POST /runs` → `{ "command": "maestro test" }` → `{ "id": 1, "started_at": "2024-05-06T10:00:00Z" }`
- `POST /runs/{id}/samples` → `[{ "ts": 1714980000.0, "cpu_percent": 12.4, "rss_mb": 230.5 }, ...]`
- `PATCH /runs/{id}/finish` → `{ "exit_code": 0 }` → Run + `run_stats`
- `GET /runs` → Son 50 koşu + istatistikleri
- `GET /runs/{id}` → Tek koşu ayrıntısı + run_stats
- `GET /runs/{id}/samples?downsample=true&step=5`
- `GET /compare?current=12&baseline=latest-success`

`run_stats` değerleri NumPy ile hesaplanan ortalama, p95, maksimum CPU/RAM ve süreyi içerir. AI yorumları Türkçe kısa metinler üretir ve ortalama CPU %80 üzerindeyse uyarı verir.

## Kullanım Akışı

1. CLI `POST /runs` ile id alır, komutu `subprocess` ile çalıştırır.
2. `psutil` ile ana süreç + alt süreçlerin CPU% & RSS MB değerleri 1 sn aralıkla toplanır.
3. Her 10 örnek backend'e toplu gönderilir.
4. Komut tamamlanınca `PATCH /runs/{id}/finish` ile çıkış kodu iletilir, backend istatistikleri hesaplar.
5. Frontend RunList → yeni koşu, RunDetail → trend grafikleri + AI yorumu, Compare → iki koşu üst üste.

## Bilinen Sınırlamalar

- Kimlik doğrulama yok; erişim tamamen lokaal.
- CLI örnek gönderimleri kalıcı olarak kuyruğa alınmaz; uzun süreli backend kesintisinde veri kaybı olabilir.
- Karşılaştırma ekranında örnekler örnek indeksine göre hizalanır (mutlak zaman ekseni yok).
- PostgreSQL kalite kontrolü için otomatik test bulunmuyor; alembic migration'ı çalıştırmak gerekiyor.

## Klasör Yapısı

```
backend/    FastAPI uygulaması ve Alembic migration'ları
cli/        Python CLI paketi
frontend/   Vite + React arayüzü
README.md   Bu dosya
```
