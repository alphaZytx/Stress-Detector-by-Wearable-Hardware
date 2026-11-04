#!/usr/bin/env python3
"""Standalone local serial monitor for the NodeMCU stress wearable.

Run from the repository root:
    .venv/bin/python scripts/hardware_monitor.py

It listens to the line format printed by ``correct_code.txt`` and serves an
independent dashboard at http://127.0.0.1:8765.  It does not start or change
the main stress-detection application.
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Any

import serial
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

PORT = "/dev/cu.usbserial-A5069RR4"
BAUDRATE = 115200
HOST = "127.0.0.1"
PORT_NUMBER = 8765

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("hardware-monitor")

SENSOR_LINE = re.compile(
    r"BPM:\s*(?P<bpm>[\d.]+)\s*\|\s*"
    r"SPO2:\s*(?P<spo2>[\d.]+)\s*\|\s*"
    r"ObjTemp:\s*(?P<object_temp>NA|[-\d.]+)\s*\|\s*"
    r"AmbTemp:\s*(?P<ambient_temp>NA|[-\d.]+)\s*\|\s*"
    r"GSR:\s*(?P<gsr>[-\d.]+)\s*\|\s*"
    r"IR:\s*(?P<ir>[-\d.]+)(?P<no_finger>\s*\|\s*No finger)?"
)


def _number(value: str) -> float | None:
    return None if value == "NA" else float(value)


def parse_sensor_line(line: str) -> dict[str, Any] | None:
    """Parse one exact line emitted by the corrected NodeMCU sketch."""
    match = SENSOR_LINE.search(line)
    if not match:
        return None
    groups = match.groupdict()
    finger_present = not bool(groups["no_finger"])
    return {
        "bpm": _number(groups["bpm"]),
        "spo2": _number(groups["spo2"]),
        "object_temp_c": _number(groups["object_temp"]) if finger_present else None,
        "ambient_temp_c": _number(groups["ambient_temp"]),
        "gsr_us": _number(groups["gsr"]),
        "ir": _number(groups["ir"]),
        "finger_present": finger_present,
    }


class SerialMonitor:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._read_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)

    def _emit(self, event: dict[str, Any]) -> None:
        self.loop.call_soon_threadsafe(self.events.put_nowait, event)

    def _read_forever(self) -> None:
        while not self.stop_event.is_set():
            try:
                with serial.Serial(PORT, BAUDRATE, timeout=1) as device:
                    logger.info("Connected to %s at %d baud", PORT, BAUDRATE)
                    self._emit({"type": "status", "connected": True, "message": "Connected to NodeMCU"})
                    while not self.stop_event.is_set():
                        raw = device.readline()
                        if not raw:
                            continue
                        line = raw.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        self._emit({"type": "serial", "line": line, "at": int(time.time() * 1000)})
                        sample = parse_sensor_line(line)
                        if sample is not None:
                            sample["at"] = int(time.time() * 1000)
                            self._emit({"type": "sample", "data": sample})
            except (serial.SerialException, OSError) as exc:
                message = f"Waiting for serial port: {exc}"
                logger.warning(message)
                self._emit({"type": "status", "connected": False, "message": message})
                self.stop_event.wait(2)


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wearable hardware monitor</title>
<style>
:root{color-scheme:dark;--bg:#07101d;--card:#101d2d;--line:#263a52;--text:#e7f0fb;--muted:#91a6be;--good:#44d3a1;--warn:#ffc267}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#112b45,var(--bg) 56%);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--text)}main{max-width:1160px;margin:auto;padding:32px 20px}h1{font:700 26px ui-sans-serif,system-ui;margin:0 0 7px}.sub{color:var(--muted);margin:0 0 24px}.state{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:7px 11px;color:var(--warn);font-size:12px}.state.on{color:var(--good)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:13px;margin:22px 0}.card{background:#101d2de8;border:1px solid var(--line);border-radius:14px;padding:18px;min-height:112px}.label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}.value{font-size:29px;font-weight:700;margin-top:13px}.unit{font-size:13px;color:var(--muted)}section{background:#08131f;border:1px solid var(--line);border-radius:14px;overflow:hidden}section header{padding:13px 16px;border-bottom:1px solid var(--line);font:600 13px ui-sans-serif,system-ui;color:var(--muted)}pre{margin:0;padding:16px;height:360px;overflow:auto;color:#cde0f2;white-space:pre-wrap;font-size:13px;line-height:1.55}.empty{color:var(--muted)}@media(max-width:500px){main{padding:22px 13px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.value{font-size:23px}}
</style></head><body><main><h1>Wearable hardware monitor</h1><p class="sub">NodeMCU 1.0 · <code>/dev/cu.usbserial-A5069RR4</code> · 115200 baud</p><span id="state" class="state">Starting serial reader…</span><div class="grid">
<div class="card"><div class="label">Heart rate</div><div class="value" id="bpm">— <span class="unit">BPM</span></div></div>
<div class="card"><div class="label">Blood oxygen</div><div class="value" id="spo2">— <span class="unit">%</span></div></div>
<div class="card"><div class="label">Object temperature</div><div class="value" id="object_temp_c">— <span class="unit">°C</span></div></div>
<div class="card"><div class="label">Ambient temperature</div><div class="value" id="ambient_temp_c">— <span class="unit">°C</span></div></div>
<div class="card"><div class="label">GSR</div><div class="value" id="gsr_us">— <span class="unit">µS</span></div></div>
<div class="card"><div class="label">PPG infrared</div><div class="value" id="ir">—</div></div>
<div class="card"><div class="label">Finger detection</div><div class="value" id="finger_present">—</div></div>
</div><section><header>Live serial monitor — newest lines appear below</header><pre id="log"><span class="empty">Waiting for serial data…</span></pre></section></main>
<script>
const log=document.querySelector('#log'),state=document.querySelector('#state');let first=true;
const fmt=(v,d=2)=>v==null?'—':Number(v).toFixed(d);
function append(line){if(first){log.textContent='';first=false}log.textContent+=line+'\n';if(log.textContent.length>24000)log.textContent=log.textContent.slice(-18000);log.scrollTop=log.scrollHeight}
function connect(){const ws=new WebSocket(`ws://${location.host}/ws`);ws.onopen=()=>{state.textContent='Dashboard connected';state.className='state on'};ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==='status'){state.textContent=m.message;state.className='state '+(m.connected?'on':'')}if(m.type==='serial')append(m.line);if(m.type==='sample'){const d=m.data;for(const k of ['bpm','spo2','object_temp_c','ambient_temp_c','gsr_us'])document.getElementById(k).innerHTML=fmt(d[k])+' <span class="unit">'+({bpm:'BPM',spo2:'%',object_temp_c:'°C',ambient_temp_c:'°C',gsr_us:'µS'}[k])+'</span>';document.getElementById('ir').textContent=fmt(d.ir,0);document.getElementById('finger_present').textContent=d.finger_present?'Present':'Not detected'}};ws.onclose=()=>{state.textContent='Dashboard reconnecting…';state.className='state';setTimeout(connect,1000)}}connect();
</script></body></html>'''


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor = SerialMonitor(asyncio.get_running_loop())
    app.state.monitor = monitor
    app.state.clients = set()
    monitor.start()

    async def broadcast() -> None:
        while True:
            event = await monitor.events.get()
            for client in list(app.state.clients):
                try:
                    await client.send_json(event)
                except Exception:
                    app.state.clients.discard(client)

    task = asyncio.create_task(broadcast())
    try:
        yield
    finally:
        task.cancel()
        monitor.stop()


app = FastAPI(title="Wearable Hardware Monitor", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return PAGE


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "serial_port": PORT}


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    await ws.accept()
    ws.app.state.clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws.app.state.clients.discard(ws)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT_NUMBER, log_level="info")
