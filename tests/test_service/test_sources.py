import asyncio
import json

import pandas as pd

from stress_detection.service.config import (
    CsvReplayConfig,
    SerialConfig,
    SyntheticConfig,
    TcpConfig,
)
from stress_detection.service.sources import build_source
from stress_detection.service.sources.csv_replay import CsvReplaySource
from stress_detection.service.sources.serial_source import SerialSource
from stress_detection.service.sources.synthetic import SyntheticSource
from stress_detection.service.sources.tcp_source import TcpSource


# ── helpers ───────────────────────────────────────────────────────────────────

async def _collect(source, n):
    """Collect up to n samples, then stop. Handles infinite (looping) streams."""
    out = []
    async for s in source.stream():
        out.append(s)
        if len(out) >= n:
            await source.stop()
            break
    return out


async def _collect_all(source):
    """Collect every sample from a finite (non-looping) stream."""
    out = []
    async for s in source.stream():
        out.append(s)
    return out


def _write_csv(path, rows):
    cols = [
        "timestamp", "bpm", "avg_bpm", "temp_c", "gsr", "label",
    ]
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)


def _base_row(**over):
    row = {
        "timestamp": 1000, "bpm": 75.0, "avg_bpm": 74,
        "temp_c": 36.5, "gsr": 100, "label": "baseline",
    }
    row.update(over)
    return row


# ── SyntheticSource ──────────────────────────────────────────────────────────

def _synthetic_cfg(**over):
    values = {
        "speed": 100_000.0,
        "seed": 42,
        "baseline_s": 3,
        "stress_s": 3,
        "recovery_s": 3,
    }
    values.update(over)
    return SyntheticConfig(**values)


def test_synthetic_source_cycles_phases_and_timestamps():
    samples = asyncio.run(_collect(SyntheticSource(_synthetic_cfg()), 9))
    assert [s.timestamp_ms for s in samples] == [i * 1000 for i in range(9)]
    assert [s.source_label for s in samples] == [
        "baseline", "baseline", "baseline",
        "stress", "stress", "stress",
        "recovery", "recovery", "recovery",
    ]


def test_synthetic_source_has_hardware_shaped_values():
    samples = asyncio.run(_collect(SyntheticSource(_synthetic_cfg()), 30))
    assert all(s.bpm is None or 40 <= s.bpm <= 200 for s in samples)
    assert all(s.gsr > 0 for s in samples)
    assert all(30.0 <= s.temp_c <= 40.0 for s in samples)


def test_synthetic_source_is_reproducible_for_same_seed():
    first = asyncio.run(_collect(SyntheticSource(_synthetic_cfg(seed=7)), 5))
    second = asyncio.run(_collect(SyntheticSource(_synthetic_cfg(seed=7)), 5))
    assert [s.to_dict() for s in first] == [s.to_dict() for s in second]


# ── CsvReplaySource ───────────────────────────────────────────────────────────

def test_csv_replay_yields_expected_count(tmp_path):
    csv = tmp_path / "small.csv"
    _write_csv(csv, [_base_row(gsr=g) for g in (10, 20, 30, 40)])
    cfg = CsvReplayConfig(files=[csv], loop=False, speed=100.0)
    src = CsvReplaySource(cfg)
    samples = asyncio.run(_collect_all(src))
    assert len(samples) == 4
    assert [s.gsr for s in samples] == [10, 20, 30, 40]


def test_csv_replay_invalid_bpm_becomes_none(tmp_path):
    csv = tmp_path / "bpm.csv"
    _write_csv(csv, [_base_row(bpm=0.0), _base_row(bpm=80.0), _base_row(bpm=300.0)])
    cfg = CsvReplayConfig(files=[csv], loop=False, speed=100.0)
    samples = asyncio.run(_collect_all(CsvReplaySource(cfg)))
    assert samples[0].bpm is None     # 0 → invalid
    assert samples[1].bpm == 80.0     # in range
    assert samples[2].bpm is None     # 300 → out of [40,200]


def test_csv_replay_timestamps_are_service_relative(tmp_path):
    csv = tmp_path / "ts.csv"
    _write_csv(csv, [_base_row(timestamp=50000), _base_row(timestamp=99999)])
    cfg = CsvReplayConfig(files=[csv], loop=False, speed=100.0)
    samples = asyncio.run(_collect_all(CsvReplaySource(cfg)))
    # Original CSV timestamps ignored; service time starts at 0, +1000/sample.
    assert samples[0].timestamp_ms == 0
    assert samples[1].timestamp_ms == 1000


def test_csv_replay_speed_runs_fast(tmp_path):
    # speed=100 → 30 samples should take well under a second of wall time.
    csv = tmp_path / "fast.csv"
    _write_csv(csv, [_base_row() for _ in range(30)])
    cfg = CsvReplayConfig(files=[csv], loop=False, speed=100.0)

    import time
    t0 = time.monotonic()
    samples = asyncio.run(_collect_all(CsvReplaySource(cfg)))
    elapsed = time.monotonic() - t0
    assert len(samples) == 30
    assert elapsed < 2.0


def test_csv_replay_loops(tmp_path):
    csv = tmp_path / "loop.csv"
    _write_csv(csv, [_base_row(gsr=11), _base_row(gsr=22), _base_row(gsr=33)])
    cfg = CsvReplayConfig(files=[csv], loop=True, speed=100.0)
    samples = asyncio.run(_collect(CsvReplaySource(cfg), 4))
    assert len(samples) == 4
    # 4th sample wraps back to the first row.
    assert samples[3].gsr == samples[0].gsr == 11
    assert samples[3].timestamp_ms == 3000  # time keeps increasing across the wrap


def test_csv_replay_multiple_files_in_order(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    _write_csv(a, [_base_row(gsr=1, label="baseline")])
    _write_csv(b, [_base_row(gsr=2, label="stress")])
    cfg = CsvReplayConfig(files=[a, b], loop=False, speed=100.0)
    samples = asyncio.run(_collect_all(CsvReplaySource(cfg)))
    assert [s.gsr for s in samples] == [1, 2]
    assert [s.source_label for s in samples] == ["baseline", "stress"]


# ── TcpSource ─────────────────────────────────────────────────────────────────

def test_tcp_source_parses_json_lines():
    payloads = [
        {"timestamp_ms": 1234, "bpm": 72, "avg_bpm": 71, "temp_c": 34.2,
         "gsr": 68},
        {"timestamp_ms": 2234, "bpm": 300, "avg_bpm": 70, "temp_c": 34.3,
         "gsr": 70},
    ]

    async def run():
        async def handle(reader, writer):
            for p in payloads:
                writer.write((json.dumps(p) + "\n").encode())
            await writer.drain()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        src = TcpSource(TcpConfig(host="127.0.0.1", port=port))
        got = await _collect(src, 2)
        server.close()
        await server.wait_closed()
        return got

    samples = asyncio.run(run())
    assert len(samples) == 2
    assert samples[0].timestamp_ms == 1234   # payload owns timestamp on TCP
    assert samples[0].bpm == 72
    assert samples[1].bpm is None            # 300 → invalid via valid_bpm


# ── SerialSource ──────────────────────────────────────────────────────────────

class _FakeSerial:
    """Minimal stand-in for pyserial.Serial emitting a few CSV lines.

    If ``raise_after`` is set, readline() raises once after that many reads to
    simulate the USB device being unplugged mid-stream.
    """

    def __init__(self, lines, raise_after=None):
        self._lines = list(lines)
        self._reads = 0
        self._raise_after = raise_after
        self.closed = False

    def readline(self):
        if self._raise_after is not None and self._reads == self._raise_after:
            self._raise_after = None  # raise just once
            raise OSError("device disconnected")
        self._reads += 1
        if self._lines:
            return self._lines.pop(0)
        return b""

    def close(self):
        self.closed = True


def _line(bpm=75.0, gsr=98, temp=36.5):
    return f"3743,{bpm},74,{gsr},{temp}\n".encode()


def test_serial_source_parses_full_csv():
    lines = [_line(bpm=75.0, gsr=98), _line(bpm=0, gsr=99)]
    src = SerialSource(SerialConfig(port="/dev/null", baudrate=115200))
    src._serial = _FakeSerial(lines)
    src._running = True

    samples = asyncio.run(_collect(src, 2))
    assert len(samples) == 2
    assert samples[0].bpm == 75.0
    assert samples[0].gsr == 98.0
    assert samples[1].bpm is None              # bpm=0 → invalid
    # Fixed 1 Hz stream clock, independent of the firmware's own timestamp.
    assert samples[0].timestamp_ms == 0
    assert samples[1].timestamp_ms == 1000


def test_serial_source_accepts_optional_tag():
    src = SerialSource(SerialConfig(port="/dev/null", baudrate=115200))
    src._serial = _FakeSerial([b"DATA,3743,80.0,74,100,36.5\n"])
    src._running = True
    samples = asyncio.run(_collect(src, 1))
    assert len(samples) == 1
    s = samples[0]
    assert s.bpm == 80.0 and s.gsr == 100.0


def test_serial_source_parses_current_nodemcu_line():
    src = SerialSource(SerialConfig(port="/dev/null", baudrate=115200))
    sample = src._parse_line(
        "BPM: 76 | SPO2: 91.2 | ObjTemp: 34.99 | AmbTemp: 27.12 | "
        "GSR: 100.76 | IR: 56564"
    )
    assert sample is not None
    assert sample.bpm == 76.0
    assert sample.avg_bpm == 76.0
    assert sample.temp_c == 34.99
    assert sample.ambient_temp_c == 27.12
    assert sample.gsr == 100.76
    assert sample.ir == 56564.0
    assert sample.finger_present is True
    assert sample.spo2 == 91.2


def test_serial_source_no_finger_hides_object_temperature_but_keeps_ambient():
    src = SerialSource(SerialConfig(port="/dev/null", baudrate=115200))
    sample = src._parse_line(
        "BPM: 0 | SPO2: 0.0 | ObjTemp: 24.99 | AmbTemp: 27.12 | "
        "GSR: 100.76 | IR: 564 | No finger"
    )
    assert sample is not None
    assert sample.bpm is None
    assert sample.avg_bpm is None
    assert sample.spo2 == 0.0
    assert sample.temp_c is None
    assert sample.ambient_temp_c == 27.12
    assert sample.finger_present is False


def test_serial_source_skips_header_and_malformed():
    lines = [
        b"timestamp,bpm,avg_bpm,gsr,temp_c\n",
        b"garbage,not,a,csv\n",          # too few fields → skipped
        _line(bpm=88.0, gsr=120),         # the only valid line
    ]
    src = SerialSource(SerialConfig(port="/dev/null", baudrate=115200))
    src._serial = _FakeSerial(lines)
    src._running = True
    samples = asyncio.run(_collect(src, 1))
    assert len(samples) == 1
    assert samples[0].bpm == 88.0


def test_serial_source_parse_line_rejects_short():
    src = SerialSource(SerialConfig(port="/dev/null", baudrate=115200))
    assert src._parse_line("garbage,not,a,csv") is None
    assert src._parse_line("") is None


def test_serial_source_reconnects_after_read_error():
    # First handle raises on the 2nd read (unplug); reconnect opens a 2nd handle.
    first = _FakeSerial([_line(bpm=70.0, gsr=50)], raise_after=1)
    second = _FakeSerial([_line(bpm=90.0, gsr=150)])
    src = SerialSource(SerialConfig(port="/dev/null", baudrate=115200))
    src._serial = first
    src._running = True
    # Patch the (re)open to hand back the second fake without touching real I/O.
    src._open = lambda: second  # type: ignore[method-assign]

    samples = asyncio.run(_collect(src, 2))
    assert [s.bpm for s in samples] == [70.0, 90.0]
    assert first.closed is True  # old handle closed before reconnect


def test_serial_source_missing_port_yields_empty():
    # A port that can't open must not crash - stream is simply empty.
    src = SerialSource(SerialConfig(port="/nonexistent/port", baudrate=115200))
    samples = asyncio.run(_collect_all(src))
    assert samples == []


# ── Factory ───────────────────────────────────────────────────────────────────

def test_build_source_constructs_each_type():
    from stress_detection.service.config import get_service_config

    cfg = get_service_config()

    cfg.input.source = "synthetic"
    assert isinstance(build_source(cfg), SyntheticSource)

    cfg.input.source = "csv_replay"
    assert isinstance(build_source(cfg), CsvReplaySource)

    cfg.input.source = "serial"
    assert isinstance(build_source(cfg), SerialSource)

    cfg.input.source = "tcp"
    assert isinstance(build_source(cfg), TcpSource)

    cfg.input.source = "synthetic"  # restore singleton state


def test_build_source_rejects_unknown():
    import pytest

    from stress_detection.service.config import get_service_config

    sc = get_service_config()
    sc.input.source = "bogus"
    with pytest.raises(ValueError):
        build_source(sc)
    sc.input.source = "synthetic"  # restore singleton state
