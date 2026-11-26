#!/usr/bin/env python3
"""Agente de infraestructura: manda CPU, RAM, ancho de banda y temperatura a OpenObserve cada N segundos."""
import base64
import glob
import json
import os
import random
import socket
import sys
import time
import urllib.request
from datetime import datetime, timezone

import psutil

OO_URL = os.getenv("OO_URL", "http://localhost:5080/api/default")
USER = os.getenv("OTLP_USER", "")
PASS = os.getenv("OTLP_PASS", "")
STREAM = os.getenv("INFRA_STREAM", "infra")
INTERVAL = int(os.getenv("INFRA_INTERVAL", "10"))
HOST = os.getenv("INFRA_HOST", socket.gethostname())


def read_temperature(cpu_percent):
    """Sensor real si existe; si no (caso normal en EC2), valor estimado a partir de la carga de CPU."""
    try:
        if hasattr(psutil, "sensors_temperatures"):
            for entries in psutil.sensors_temperatures().values():
                if entries:
                    return round(entries[0].current, 1), "sensor"
    except Exception:
        pass
    for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            return round(int(open(path).read().strip()) / 1000, 1), "sensor"
        except Exception:
            continue
    return round(40 + cpu_percent * 0.35 + random.uniform(-0.5, 0.5), 1), "estimated"


def send(rows):
    token = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
    req = urllib.request.Request(
        f"{OO_URL}/{STREAM}/_json",
        data=json.dumps(rows).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Basic {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


def main():
    once = "--once" in sys.argv
    psutil.cpu_percent(None)
    prev = psutil.net_io_counters()
    prev_t = time.time()
    while True:
        time.sleep(1 if once else INTERVAL)
        now = time.time()
        net = psutil.net_io_counters()
        dt = max(now - prev_t, 0.001)
        sent_kbps = (net.bytes_sent - prev.bytes_sent) * 8 / 1000 / dt
        recv_kbps = (net.bytes_recv - prev.bytes_recv) * 8 / 1000 / dt
        prev, prev_t = net, now

        cpu = psutil.cpu_percent(None)
        mem = psutil.virtual_memory()
        temp, temp_src = read_temperature(cpu)
        row = {
            "host": HOST,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cpu_percent": cpu,
            "load_1m": round(os.getloadavg()[0], 2),
            "ram_percent": mem.percent,
            "ram_used_mb": round(mem.used / 1024 / 1024),
            "ram_total_mb": round(mem.total / 1024 / 1024),
            "disk_percent": psutil.disk_usage("/").percent,
            "net_sent_kbps": round(sent_kbps, 2),
            "net_recv_kbps": round(recv_kbps, 2),
            "net_total_kbps": round(sent_kbps + recv_kbps, 2),
            "temperature_c": temp,
            "temperature_source": temp_src,
        }
        try:
            status = send([row])
            print(f"[{row['timestamp']}] enviado ({status}) cpu={cpu}% ram={mem.percent}% temp={temp}C({temp_src})", flush=True)
        except Exception as e:
            print(f"[{row['timestamp']}] error al enviar: {e}", flush=True)
        if once:
            print(json.dumps(row, indent=1))
            break


if __name__ == "__main__":
    main()
