#!/usr/bin/env python3
"""Envia metricas de infraestructura de la EC2 a OpenObserve (stream 'infra') cada N segundos.
Solo usa psutil + libreria estandar. Credenciales por variables de entorno (.env de la app)."""
import base64, json, os, random, socket, sys, time, urllib.request
from datetime import datetime, timezone
import psutil

URL = os.environ.get("OO_INFRA_URL", "http://localhost:5080/api/default/infra/_json")
USER = os.environ.get("OTLP_USER", "admin@proyecto.com")
PASS = os.environ.get("OTLP_PASS", "Proyecto2026!")
INTERVAL = int(os.environ.get("INFRA_INTERVAL", "10"))
HOST = os.environ.get("INFRA_HOST", socket.gethostname())
AUTH = "Basic " + base64.b64encode(f"{USER}:{PASS}".encode()).decode()

_last_temp = 40.0

def read_temperature(cpu):
    """Temperatura real si el sistema la expone; si no (EC2 no la expone), valor SIMULADO."""
    global _last_temp
    try:
        temps = psutil.sensors_temperatures()
        vals = [t.current for lst in temps.values() for t in lst if t.current]
        if vals:
            return round(max(vals), 1), "sensor"
    except Exception:
        pass
    target = 38.0 + cpu * 0.35 + random.uniform(-0.8, 0.8)
    _last_temp = round(_last_temp * 0.6 + target * 0.4, 1)
    return _last_temp, "simulated"

def sample(prev, now):
    net = psutil.net_io_counters()
    dt = max(now - prev["t"], 0.001)
    in_kbps = round((net.bytes_recv - prev["rx"]) / 1024 / dt, 2)
    out_kbps = round((net.bytes_sent - prev["tx"]) / 1024 / dt, 2)
    prev.update(t=now, rx=net.bytes_recv, tx=net.bytes_sent)
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    temp, src = read_temperature(cpu)
    return {
        "host": HOST,
        "cpu_percent": cpu,
        "ram_percent": mem.percent,
        "ram_used_mb": round(mem.used / 1048576, 1),
        "ram_total_mb": round(mem.total / 1048576, 1),
        "disk_percent": psutil.disk_usage("/").percent,
        "net_in_kbps": in_kbps,
        "net_out_kbps": out_kbps,
        "net_bytes_recv": net.bytes_recv,
        "net_bytes_sent": net.bytes_sent,
        "load_1m": round(os.getloadavg()[0], 2),
        "temp_c": temp,
        "temp_source": src,
    }

def send(payload):
    req = urllib.request.Request(URL, data=json.dumps([payload]).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": AUTH})
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.status

def main():
    dry = "--dry-run" in sys.argv
    net = psutil.net_io_counters()
    prev = {"t": time.time(), "rx": net.bytes_recv, "tx": net.bytes_sent}
    psutil.cpu_percent(interval=None)
    time.sleep(2 if dry else INTERVAL)
    while True:
        p = sample(prev, time.time())
        if dry:
            print(json.dumps(p, indent=2)); return
        try:
            send(p)
        except Exception as e:
            print(f"[infra_monitor] error enviando: {e}", flush=True)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
