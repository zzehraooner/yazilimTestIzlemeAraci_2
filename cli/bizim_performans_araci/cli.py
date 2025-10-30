import argparse
import os
import subprocess
import sys
import time
from typing import Dict, List, Optional, Set

import psutil
import requests

DEFAULT_BACKEND_URL = "http://localhost:8000"
BATCH_SIZE = 10
SAMPLE_INTERVAL_SECONDS = 1.0
MAX_SAMPLE_RETRY_ATTEMPTS = 3


class ApiClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0):
        self.base_url = (base_url or os.getenv("BIZIM_BACKEND_URL") or DEFAULT_BACKEND_URL).rstrip("/")
        self.timeout = timeout

    def create_run(self, command: str, baseline_run_id: Optional[int] = None) -> Dict:
        payload: Dict[str, object] = {"command": command}
        if baseline_run_id is not None:
            payload["baseline_run_id"] = baseline_run_id

        response = self._request("POST", "/runs", json=payload)
        return response.json()

    def post_samples(self, run_id: int, samples: List[Dict[str, float]]) -> bool:
        if not samples:
            return True

        endpoint = f"/runs/{run_id}/samples"
        for attempt in range(MAX_SAMPLE_RETRY_ATTEMPTS):
            try:
                response = self._request("POST", endpoint, json=samples)
                if response.status_code in (204, 200):
                    return True
            except requests.RequestException as exc:
                backoff_seconds = 2 ** attempt
                _log(f"Örnek gönderimi başarısız (deneme {attempt + 1}): {exc}; {backoff_seconds}s sonra yeniden denenecek.")
                time.sleep(backoff_seconds)
        return False

    def finish_run(self, run_id: int, exit_code: int) -> Dict:
        response = self._request("PATCH", f"/runs/{run_id}/finish", json={"exit_code": exit_code})
        return response.json()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.HTTPError:
            _log(f"HTTP hatası: {response.status_code} - {response.text}")
            raise
        except requests.RequestException as exc:
            _log(f"İstek hatası: {exc}")
            raise


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bizim-performans-araci",
        description="Komut çalıştırıp CPU/RAM metriklerini backend'e gönderen CLI kaplaması.",
    )
    parser.add_argument("--backend", help="Backend taban URL'si (varsayılan: http://localhost:8000)")

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Komutu performans takibiyle çalıştır")
    run_parser.add_argument("target_command", help="Çalıştırılacak komut (ör. \"maestro test senaryolarim.yml\")")
    run_parser.add_argument("--baseline", type=int, help="Karşılaştırma için baz koşu ID'si (opsiyonel)")
    run_parser.add_argument("--interval", type=float, default=SAMPLE_INTERVAL_SECONDS, help="Örnekleme aralığı (saniye)")
    run_parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Backend'e toplu gönderim boyutu")
    run_parser.set_defaults(func=execute_run)

    return parser


def execute_run(args: argparse.Namespace) -> None:
    api = ApiClient(args.backend)
    command = args.target_command
    _log(f"Komut için koşu oluşturuluyor: {command}")

    try:
        creation = api.create_run(command, baseline_run_id=args.baseline)
    except requests.RequestException:
        _log("Koşu başlatılamadı; çıkılıyor.")
        sys.exit(1)

    run_id = creation["id"]
    _log(f"Koşu #{run_id} başlatıldı ({creation['started_at']}).")

    process = subprocess.Popen(command, shell=True)
    exit_code = 0
    buffer: List[Dict[str, float]] = []
    try:
        exit_code = monitor_process(
            process,
            run_id,
            api,
            buffer=buffer,
            interval=max(args.interval, 0.1),
            batch_size=max(args.batch_size, 1),
        )
    except KeyboardInterrupt:
        _log("Kullanıcı tarafından kesildi; süreç sonlandırılıyor...")
        process.terminate()
        exit_code = process.wait()
    finally:
        if buffer:
            if api.post_samples(run_id, list(buffer)):
                buffer.clear()
            else:
                _log("Kalan örnekler gönderilemedi.")

        try:
            summary = api.finish_run(run_id, exit_code)
            _log(f"Koşu #{run_id} tamamlandı; çıkış kodu {exit_code}.")
            if summary.get("stats"):
                stats = summary["stats"]
                avg_cpu = stats.get("avg_cpu")
                duration = stats.get("duration_s")
                _log(
                    f"Özet - ort. CPU: {avg_cpu:.1f}% | süre: {duration:.1f}s"
                    if avg_cpu is not None and duration is not None
                    else "Özet bilgisi mevcut değil."
                )
        except requests.RequestException:
            _log("Koşu bitişi backend'e bildirilemedi.")


def monitor_process(
    process: subprocess.Popen,
    run_id: int,
    api: ApiClient,
    buffer: List[Dict[str, float]],
    interval: float,
    batch_size: int,
) -> int:
    try:
        proc = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return process.wait()

    primed: Set[int] = set()
    prime_process(proc, primed)

    while True:
        if process.poll() is not None:
            break

        time.sleep(interval)
        sample = collect_sample(proc, primed)
        if sample:
            buffer.append(sample)
        if len(buffer) >= batch_size:
            flush_buffer(api, run_id, buffer)

    # capture one more snapshot after the process stops to get final memory usage
    final_sample = collect_sample(proc, primed)
    if final_sample:
        buffer.append(final_sample)
        flush_buffer(api, run_id, buffer)

    return process.wait()


def collect_sample(proc: psutil.Process, primed: Set[int]) -> Optional[Dict[str, float]]:
    processes = [proc]
    try:
        processes.extend(proc.children(recursive=True))
    except (psutil.Error, Exception):
        pass

    total_cpu = 0.0
    total_rss = 0
    measured = False
    timestamp = time.time()

    for p in processes:
        if p.pid not in primed:
            prime_process(p, primed)
            continue
        try:
            cpu = p.cpu_percent(interval=None)
            mem = p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        total_cpu += cpu
        total_rss += mem
        measured = True

    if not measured:
        return None

    rss_mb = round(total_rss / (1024 * 1024), 2)
    return {"ts": timestamp, "cpu_percent": round(total_cpu, 2), "rss_mb": rss_mb}


def prime_process(proc: psutil.Process, primed: Set[int]) -> None:
    try:
        proc.cpu_percent(interval=None)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return
    primed.add(proc.pid)


def flush_buffer(api: ApiClient, run_id: int, buffer: List[Dict[str, float]]) -> None:
    if not buffer:
        return
    payload = list(buffer)
    if api.post_samples(run_id, payload):
        buffer.clear()


def _log(message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    sys.stderr.write(f"[{timestamp}] {message}\n")
    sys.stderr.flush()


if __name__ == "__main__":
    main()
