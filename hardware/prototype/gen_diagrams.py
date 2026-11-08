#!/usr/bin/env python3
"""Generate the prototype schematic and perfboard placement guide.

    python hardware/prototype/gen_diagrams.py

Writes schematic.svg, perfboard.svg and netlist.json next to this file. The SVGs use
CSS classes; standalone files embed a light-theme stylesheet so they render anywhere.
The perfboard part placement (PARTS) is the single source for the layout drawing and
the hole-coordinate net list.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent

STANDALONE_CSS = """
.ink{stroke:#1d2a2c;fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.inkf{fill:#1d2a2c}
.body{fill:#ffffff;stroke:#1d2a2c;stroke-width:1.6}
.frame{fill:none;stroke:#9aa7a3;stroke-width:1;stroke-dasharray:4 4}
.ftitle{font:600 13px 'IBM Plex Sans',Arial,sans-serif;fill:#5a6966;letter-spacing:.06em}
.t{font:11px 'IBM Plex Mono',monospace;fill:#1d2a2c}
.tb{font:600 12px 'IBM Plex Sans',Arial,sans-serif;fill:#1d2a2c}
.ts{font:10px 'IBM Plex Mono',monospace;fill:#5a6966}
.flag{fill:#f3e6da;stroke:#a8582a;stroke-width:1.2}
.flagt{font:600 10.5px 'IBM Plex Mono',monospace;fill:#7a3b17}
.dot{fill:#1d2a2c}
.nc{stroke:#c0392b;stroke-width:2}
.warn{font:10px 'IBM Plex Mono',monospace;fill:#b03a20}
.board{fill:#e9eedf;stroke:#9aa98f;stroke-width:1}
.hole{fill:#c3cbb7}
.fp{fill:rgba(255,255,255,.55);stroke:#425053;stroke-width:1.2}
.fpl{font:600 10px 'IBM Plex Sans',Arial,sans-serif;fill:#243033}
.axis{font:9px 'IBM Plex Mono',monospace;fill:#6c7a76}
.keep{fill:rgba(192,57,43,.08);stroke:#c0392b;stroke-width:1;stroke-dasharray:3 3}
.pin{stroke:#1d2a2c;stroke-width:1}
.pin.free{fill:#ffffff}
.rat{fill:none;stroke-width:1.8;stroke-linecap:round;opacity:.85}
"""

# ============================================================================ schematic


class Svg:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def wire(self, *pts: tuple[float, float]) -> None:
        d = " ".join(f"{x},{y}" for x, y in pts)
        self.add(f'<polyline class="ink" points="{d}"/>')

    def dot(self, x: float, y: float) -> None:
        self.add(f'<circle class="dot" cx="{x}" cy="{y}" r="3"/>')

    def text(self, x: float, y: float, s: str, cls: str = "t", anchor: str = "start") -> None:
        self.add(f'<text class="{cls}" x="{x}" y="{y}" text-anchor="{anchor}">{s}</text>')

    def frame(self, x: float, y: float, w: float, h: float, title: str) -> None:
        self.add(f'<rect class="frame" x="{x}" y="{y}" width="{w}" height="{h}" rx="6"/>')
        self.text(x + 12, y + 20, title.upper(), "ftitle")

    def gnd(self, x: float, y: float) -> None:
        self.wire((x, y), (x, y + 8))
        for i, w in enumerate((20, 12, 4)):
            self.add(f'<line class="ink" x1="{x - w / 2}" y1="{y + 8 + i * 4}" x2="{x + w / 2}" y2="{y + 8 + i * 4}"/>')

    def res_v(self, x: float, y1: float, y2: float, name: str, value: str, side: str = "right") -> None:
        m = (y1 + y2) / 2
        h = max(18, (y2 - y1) - 14)
        self.wire((x, y1), (x, m - h / 2))
        self.wire((x, m + h / 2), (x, y2))
        self.add(f'<rect class="body" x="{x - 6}" y="{m - h / 2}" width="12" height="{h}" rx="1.5"/>')
        tx = x + 11 if side == "right" else x - 11
        a = "start" if side == "right" else "end"
        self.text(tx, m - 2, name, "tb", a)
        self.text(tx, m + 11, value, "ts", a)

    def cap_v(self, x: float, y1: float, y2: float, name: str, value: str, polar: bool = False,
              side: str = "right") -> None:
        m = (y1 + y2) / 2
        self.wire((x, y1), (x, m - 3))
        self.wire((x, m + 3), (x, y2))
        self.add(f'<line class="ink" x1="{x - 11}" y1="{m - 3}" x2="{x + 11}" y2="{m - 3}" stroke-width="2.4"/>')
        if polar:
            self.add(f'<path class="ink" d="M{x - 11},{m + 6} Q{x},{m + 1} {x + 11},{m + 6}" stroke-width="2.4"/>')
            self.text(x - 17, m - 6, "+", "ts", "middle")
        else:
            self.add(f'<line class="ink" x1="{x - 11}" y1="{m + 3}" x2="{x + 11}" y2="{m + 3}" stroke-width="2.4"/>')
        tx = x + 15 if side == "right" else x - 15
        a = "start" if side == "right" else "end"
        self.text(tx, m - 2, name, "tb", a)
        self.text(tx, m + 11, value, "ts", a)

    def diode_h(self, x1: float, x2: float, y: float, name: str, value: str) -> None:
        """Anode at x1, cathode at x2 (pointing right)."""
        m = (x1 + x2) / 2
        self.wire((x1, y), (m - 9, y))
        self.wire((m + 9, y), (x2, y))
        self.add(f'<polygon class="body" points="{m - 9},{y - 9} {m - 9},{y + 9} {m + 8},{y}"/>')
        self.add(f'<line class="ink" x1="{m + 9}" y1="{y - 9}" x2="{m + 9}" y2="{y + 9}" stroke-width="2.2"/>')
        self.text(m, y - 16, name, "tb", "middle")
        self.text(m, y + 24, value, "ts", "middle")

    def mosfet(self, x: float, y: float, kind: str, name: str, value: str) -> dict[str, tuple[float, float]]:
        """Gate input at (x, y). N: drain top, source bottom. P: source top, drain bottom."""
        self.wire((x, y), (x + 14, y))
        self.add(f'<line class="ink" x1="{x + 14}" y1="{y - 16}" x2="{x + 14}" y2="{y + 16}"/>')
        for a, b in ((-18, -8), (-5, 5), (8, 18)):
            self.add(f'<line class="ink" x1="{x + 20}" y1="{y + a}" x2="{x + 20}" y2="{y + b}" stroke-width="2.2"/>')
        top, bot = (x + 32, y - 32), (x + 32, y + 32)
        self.wire((x + 20, y - 13), (x + 32, y - 13), top)
        self.wire((x + 20, y + 13), (x + 32, y + 13), bot)
        if kind == "n":  # body tied to source (bottom), arrow toward channel
            self.wire((x + 20, y), (x + 32, y), (x + 32, y + 13))
            self.add(f'<polygon class="inkf" points="{x + 21},{y} {x + 28},{y - 4} {x + 28},{y + 4}"/>')
        else:  # body tied to source (top), arrow away from channel
            self.wire((x + 20, y), (x + 32, y), (x + 32, y - 13))
            self.add(f'<polygon class="inkf" points="{x + 31},{y} {x + 24},{y - 4} {x + 24},{y + 4}"/>')
        self.text(x + 40, y - 3, name, "tb")
        self.text(x + 40, y + 10, value, "ts")
        if kind == "n":
            return {"g": (x, y), "d": top, "s": bot}
        return {"g": (x, y), "s": top, "d": bot}

    def flag(self, x: float, y: float, label: str, d: str = "left") -> None:
        w = len(label) * 6.6 + 14
        h = 16
        if d == "left":
            pts = [(x, y), (x - 7, y - h / 2), (x - w, y - h / 2), (x - w, y + h / 2), (x - 7, y + h / 2)]
            tx, ty, a = x - w / 2 - 3, y + 3.8, "middle"
        elif d == "right":
            pts = [(x, y), (x + 7, y - h / 2), (x + w, y - h / 2), (x + w, y + h / 2), (x + 7, y + h / 2)]
            tx, ty, a = x + w / 2 + 3, y + 3.8, "middle"
        elif d == "down":
            pts = [(x, y), (x + w / 2, y + 6), (x + w / 2, y + 6 + h), (x - w / 2, y + 6 + h), (x - w / 2, y + 6)]
            tx, ty, a = x, y + 6 + h / 2 + 3.8, "middle"
        else:  # up
            pts = [(x, y), (x + w / 2, y - 6), (x + w / 2, y - 6 - h), (x - w / 2, y - 6 - h), (x - w / 2, y - 6)]
            tx, ty, a = x, y - 6 - h / 2 + 3.8, "middle"
        p = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        self.add(f'<polygon class="flag" points="{p}"/>')
        self.text(tx, ty, label, "flagt", a)

    def module(self, x: float, y: float, w: float, h: float, title: str,
               left: list[tuple[str, float]], right: list[tuple[str, float]], note: list[str] = ()) -> dict:
        self.add(f'<rect class="body" x="{x}" y="{y}" width="{w}" height="{h}" rx="4"/>')
        self.text(x + w / 2, y + 17, title, "tb", "middle")
        pins = {}
        for name, py in left:
            self.text(x + 7, py + 4, name, "t")
            pins[name] = (x, py)
        for name, py in right:
            self.text(x + w - 7, py + 4, name, "t", "end")
            pins[name] = (x + w, py)
        for i, line in enumerate(note):
            self.text(x + w / 2, y + h - 10 - 13 * (len(note) - 1 - i), line, "warn", "middle")
        return pins

    def battery_v(self, x: float, y1: float, y2: float, name: str, value: str) -> None:
        m = (y1 + y2) / 2
        self.wire((x, y1), (x, m - 10))
        self.wire((x, m + 10), (x, y2))
        for dy, w, sw in ((-10, 26, 1.8), (-4, 14, 3.2), (4, 26, 1.8), (10, 14, 3.2)):
            self.add(f'<line class="ink" x1="{x - w / 2}" y1="{m + dy}" x2="{x + w / 2}" y2="{m + dy}" stroke-width="{sw}"/>')
        self.text(x - 20, m - 12, "+", "ts", "middle")
        self.text(x + 20, m - 2, name, "tb")
        self.text(x + 20, m + 11, value, "ts")

    def pv_v(self, x: float, y1: float, y2: float, name: str, value: str,
             label_at: tuple[float, float] | None = None) -> None:
        m = (y1 + y2) / 2
        self.wire((x, y1), (x, m - 22))
        self.wire((x, m + 22), (x, y2))
        self.add(f'<circle class="body" cx="{x}" cy="{m}" r="22"/>')
        for dy, w, sw in ((-4, 22, 1.8), (4, 12, 3.2)):
            self.add(f'<line class="ink" x1="{x - w / 2}" y1="{m + dy}" x2="{x + w / 2}" y2="{m + dy}" stroke-width="{sw}"/>')
        for k in (0, 10):  # incoming light arrows
            ax, ay = x - 40 + k, m - 38 + k
            self.add(f'<line class="ink" x1="{ax}" y1="{ay}" x2="{ax + 14}" y2="{ay + 14}"/>')
            self.add(f'<polygon class="inkf" points="{ax + 16},{ay + 16} {ax + 8},{ay + 13} {ax + 13},{ay + 8}"/>')
        self.text(x - 26, m - 8, "+", "ts", "middle")
        lx, ly = label_at or (x + 30, m)
        self.text(lx, ly - 2, name, "tb")
        self.text(lx, ly + 11, value, "ts")

    def switch_v(self, x: float, y1: float, y2: float, name: str, value: str, side: str = "right") -> None:
        m = (y1 + y2) / 2
        self.wire((x, y1), (x, m - 12))
        self.wire((x, m + 12), (x, y2))
        self.add(f'<circle class="body" cx="{x}" cy="{m - 12}" r="2.5"/>')
        self.add(f'<circle class="body" cx="{x}" cy="{m + 12}" r="2.5"/>')
        self.add(f'<line class="ink" x1="{x}" y1="{m + 10}" x2="{x - 12}" y2="{m - 12}"/>')
        tx, a = (x + 12, "start") if side == "right" else (x - 18, "end")
        self.text(tx, m - 2, name, "tb", a)
        self.text(tx, m + 11, value, "ts", a)

    def nc(self, x: float, y: float) -> None:
        self.add(f'<line class="nc" x1="{x - 5}" y1="{y - 5}" x2="{x + 5}" y2="{y + 5}"/>')
        self.add(f'<line class="nc" x1="{x - 5}" y1="{y + 5}" x2="{x + 5}" y2="{y - 5}"/>')

    def render(self, css: str | None) -> str:
        style = f"<style>{css}</style>" if css else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'role="img" aria-label="Solar-Log prototype schematic">{style}{"".join(self.parts)}</svg>')


def schematic() -> Svg:
    s = Svg(1290, 900)

    # ------------------------------------------------------------ A: power
    s.frame(10, 10, 400, 420, "A · Power")
    s.wire((40, 150), (40, 90), (188, 90))
    s.battery_v(40, 150, 230, "BT1", "18650 protected")
    s.gnd(40, 230)
    s.text(200, 380, "CN3791 BAT+/BAT− wire", "ts", "start")
    s.text(200, 393, "straight to the holder", "ts", "start")
    s.dot(100, 90)
    s.dot(130, 90)
    s.cap_v(130, 90, 160, "C3", "10µF", polar=True)
    s.gnd(130, 160)
    u2 = s.module(188, 68, 80, 62, "U2", [("VIN", 90)], [("VOUT", 90)])
    s.text(244, 196, "MCP1700-3302 (TO-92)", "ts", "start")
    s.text(244, 208, "or HT7833 on adapter", "ts", "start")
    s.wire(u2["VOUT"], (390, 90))
    s.text(228, 118, "GND", "t", "middle")
    s.wire((228, 130), (228, 170))
    s.gnd(228, 170)
    s.dot(300, 90)
    s.dot(350, 90)
    s.cap_v(300, 90, 160, "C1", "1000µF", polar=True)
    s.gnd(300, 160)
    s.cap_v(350, 90, 160, "C2", "100nF")
    s.gnd(350, 160)
    s.text(388, 80, "3V3 → ESP32 3V3 pin", "flagt", "end")
    # divider
    s.wire((100, 90), (100, 230))
    s.res_v(100, 230, 290, "R1", "1M", side="left")
    s.dot(100, 300)
    s.wire((100, 290), (100, 310))
    s.res_v(100, 310, 370, "R2", "1M", side="left")
    s.gnd(100, 370)
    s.wire((100, 300), (230, 300))
    s.dot(160, 300)
    s.cap_v(160, 300, 370, "C4", "100nF")
    s.gnd(160, 370)
    s.flag(230, 300, "VSENSE", "right")
    s.text(60, 80, "VBAT", "flagt")

    # ------------------------------------------------------------ B: cell, Isc, charging
    s.frame(420, 10, 860, 420, "B · Reference cell, Isc measurement, charging")
    s.pv_v(450, 130, 210, "PV1", "6V 1W", label_at=(436, 252))
    s.gnd(450, 210)
    s.wire((450, 130), (450, 90), (720, 90))
    s.text(470, 82, "CELL+", "flagt")
    s.dot(500, 90)
    ina = s.module(545, 145, 110, 120, "INA219 module",
                   [("VIN+", 180), ("VIN−", 230)], [("VCC", 170), ("GND", 195), ("SDA", 220), ("SCL", 245)])
    s.wire((500, 90), (500, 180), ina["VIN+"])
    s.wire(ina["VIN−"], (520, 230), (520, 298))
    s.text(523, 275, "SHUNT_LO", "ts")
    q1 = s.mosfet(488, 330, "n", "Q1", "IRLB8721")
    s.wire((520, 298), q1["d"])
    s.gnd(*q1["s"])
    s.wire(q1["g"], (450, 330))
    s.dot(470, 330)
    s.res_v(470, 330, 395, "R3", "100k", side="left")
    s.gnd(470, 395)
    s.wire((450, 330), (450, 300))
    s.flag(450, 300, "SHORT", "up")
    for pin, net, dirn in (("VCC", "S3V3", "right"), ("SDA", "SDA", "right"), ("SCL", "SCL", "right")):
        px, py = ina[pin]
        s.wire((px, py), (px + 18, py))
        s.flag(px + 18, py, net, dirn)
    gx, gy = ina["GND"]
    s.wire((gx, gy), (gx + 18, gy))
    s.text(gx + 22, gy + 4, "GND", "ts")
    s.text(600, 288, "shunt 0.1Ω between VIN+/VIN−", "ts", "middle")

    # charge path
    s.diode_h(720, 790, 90, "D1", "1N5819")
    s.wire((790, 90), (922, 90), (922, 118))
    s.text(800, 82, "CHG_A", "ts")
    s.dot(862, 90)
    s.res_v(862, 90, 150, "R5", "100k", side="left")
    q2 = s.mosfet(890, 150, "p", "Q2", "AO3401")
    s.wire(q2["s"], (922, 118))
    s.wire((862, 150), q2["g"])
    s.dot(862, 150)
    s.wire((862, 150), (862, 238))
    q3 = s.mosfet(830, 270, "n", "Q3", "2N7000")
    s.wire((862, 238), q3["d"])
    s.gnd(*q3["s"])
    s.wire(q3["g"], (790, 270))
    s.dot(805, 270)
    s.res_v(805, 270, 335, "R6", "100k", side="left")
    s.gnd(805, 335)
    s.flag(790, 270, "CHG_EN", "left")
    s.text(870, 205, "Q2_G", "ts")
    # charger
    cn = s.module(1010, 150, 170, 190, "CN3791 MPPT (6V)",
                  [("IN+", 190), ("IN−", 230), ("CHRG", 290)], [("BAT+", 190), ("BAT−", 230)],
                  note=["remove CHRG LED", "(pin is open-drain)"])
    s.wire(q2["d"], (922, 190), cn["IN+"])
    s.text(940, 184, "CHG_IN", "ts")
    s.wire(cn["IN−"], (985, 230), (985, 240))
    s.gnd(985, 240)
    s.wire(cn["CHRG"], (950, 290), (950, 370), (935, 370))
    s.dot(950, 290)
    s.flag(935, 370, "CHG_STAT", "left")
    # pull-up R8 from CHRG node to 3V3 drawn to the right of the CHRG wire, below module
    for pin, label in (("BAT+", "VBAT"),):
        px, py = cn[pin]
        s.wire((px, py), (px + 18, py))
        s.flag(px + 18, py, label, "right")
    px, py = cn["BAT−"]
    s.wire((px, py), (px + 18, py), (px + 18, py + 10))
    s.gnd(px + 18, py + 10)
    return s


def schematic_full() -> Svg:
    s = schematic()
    # R8 pull-up: CHG_STAT node to 3V3 (GPIO34 has no internal pull-up)
    s.dot(950, 330)
    s.wire((950, 330), (985, 330), (985, 335))
    s.res_v(985, 335, 395, "R8", "100k")
    s.flag(985, 395, "3V3", "down")

    # ------------------------------------------------------------ C: sensor rail & sensors
    s.frame(10, 445, 600, 445, "C · Switched sensor rail & sensors")
    s.flag(52, 500, "3V3", "left")
    s.wire((52, 500), (142, 500), (142, 528))
    s.dot(90, 500)
    s.res_v(90, 500, 560, "R4", "10k", side="left")
    q4 = s.mosfet(110, 560, "p", "Q4", "AO3401")
    s.wire((90, 560), q4["g"])
    s.dot(90, 560)
    s.wire((90, 560), (90, 640))
    s.flag(90, 640, "RAIL_EN", "down")
    s.wire(q4["d"], (142, 610), (560, 610))
    s.text(160, 604, "S3V3  (sensor rail — off in deep sleep)", "flagt")
    s.flag(560, 610, "S3V3", "right")
    # DS3231
    ds = s.module(250, 660, 150, 185, "DS3231 (ZS-042)",
                  [("VCC", 690), ("SDA", 730), ("SCL", 770)], [("GND", 690)],
                  note=["remove charge R/diode", "and power LED", "CR2032 fitted"])
    s.wire(ds["VCC"], (220, 690), (220, 610))
    s.dot(220, 610)
    s.wire(ds["SDA"], (230, 730))
    s.flag(230, 730, "SDA", "left")
    s.wire(ds["SCL"], (230, 770))
    s.flag(230, 770, "SCL", "left")
    s.wire(ds["GND"], (420, 690), (420, 700))
    s.gnd(420, 700)
    # DS18B20
    pr = s.module(490, 660, 110, 110, "2× DS18B20",
                  [("VDD", 690), ("DQ", 715), ("GND", 740)], [])
    s.text(545, 760, "R / Y / B wires", "ts", "middle")
    s.wire(pr["VDD"], (470, 690), (470, 610))
    s.dot(470, 610)
    s.wire(pr["DQ"], (445, 715))
    s.dot(445, 715)
    s.wire((445, 610), (445, 625))
    s.dot(445, 610)
    s.res_v(445, 625, 690, "R9", "4.7k", side="left")
    s.wire((445, 690), (445, 715), (445, 800))
    s.flag(445, 800, "1W", "down")
    s.wire(pr["GND"], (480, 740), (480, 780))
    s.gnd(480, 780)
    s.text(30, 860, "INA219 VCC also on S3V3 (block B). I²C pull-ups on the modules go to S3V3.", "ts")

    # ------------------------------------------------------------ D: ESP32
    s.frame(620, 445, 660, 445, "D · ESP32 DevKitC (low-power modified)")
    left = [("3V3", 500), ("GND", 530), ("IO35", 560), ("IO34", 590), ("IO33", 620),
            ("IO25", 650), ("IO26", 680), ("IO27", 710), ("5V", 760)]
    right = [("IO21", 500), ("IO22", 530), ("IO4", 560), ("GND", 600)]
    esp = s.module(820, 470, 200, 320, "ESP32", left, [(n + " ", y) for n, y in right],
                   note=["5V/VIN and USB: not", "connected on battery"])
    nets_l = {"3V3": "3V3", "IO35": "VSENSE", "IO34": "CHG_STAT", "IO33": "BTN",
              "IO25": "RAIL_EN", "IO26": "SHORT", "IO27": "CHG_EN"}
    for pin, y in left:
        px, py = esp[pin]
        if pin == "GND":
            s.wire((px, py), (px - 40, py), (px - 40, py + 6))
            s.gnd(px - 40, py + 6)
        elif pin == "5V":
            s.wire((px, py), (px - 25, py))
            s.nc(px - 25, py)
            s.text(px - 34, py + 4, "NC", "warn", "end")
        else:
            s.wire((px, py), (px - 40, py))
            s.flag(px - 40, py, nets_l[pin], "left")
    nets_r = {"IO21 ": "SDA", "IO22 ": "SCL", "IO4 ": "1W"}
    for pin, y in right:
        px, py = esp[pin + " "]
        if pin == "GND":
            s.wire((px, py), (px + 30, py), (px + 30, py + 6))
            s.gnd(px + 30, py + 6)
        else:
            s.wire((px, py), (px + 30, py))
            s.flag(px + 30, py, nets_r[pin + " "], "right")
    s.text(920, 816, "GPIO numbers, not header positions —", "ts", "middle")
    s.text(920, 829, "see the perfboard guide for pin locations", "ts", "middle")
    # button
    s.text(1170, 630, "3V3", "flagt", "middle")
    s.wire((1170, 636), (1170, 650))
    s.res_v(1170, 650, 710, "R7", "100k")
    s.dot(1170, 720)
    s.wire((1170, 710), (1170, 740))
    s.wire((1170, 720), (1120, 720))
    s.flag(1120, 720, "BTN", "left")
    s.switch_v(1170, 740, 800, "SW1", "panel button", side="left")
    s.gnd(1170, 800)
    s.wire((1170, 720), (1240, 720), (1240, 740))
    s.cap_v(1240, 740, 800, "C5", "100nF", side="left")
    s.gnd(1240, 800)
    return s


# ============================================================================ perfboard

COLS, ROWS = 35, 27
ROW_NAMES = [chr(ord("A") + i) for i in range(26)] + ["AA"]


def hole_name(c: int, r: int) -> str:
    return f"{ROW_NAMES[r]}{c + 1}"


# DevKitC V4 / NodeMCU-32S 38-pin header order, antenna pointing right.
ESP_TOP = ["3V3", "EN", "VP", "VN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14",
           "IO12", "GND", "IO13", "SD2", "SD3", "CMD", "5V"]  # cols 26 -> 8
ESP_BOT = ["GND", "IO23", "IO22", "TX", "RX", "IO21", "GND", "IO19", "IO18", "IO5", "IO17", "IO16",
           "IO4", "IO0", "IO2", "IO15", "SD1", "SD0", "CLK"]  # cols 26 -> 8
ESP_NETS = {"3V3": "3V3", "IO34": "CHG_STAT", "IO35": "VSENSE", "IO33": "BTN", "IO25": "RAIL_EN",
            "IO26": "SHORT", "IO27": "CHG_EN", "IO22": "SCL", "IO21": "SDA", "IO4": "1W"}

# ref: (label, part, outline (c0, r0, c1, r1) in hole units or None, [(pin, c, r, net)], shape)
PARTS = [
    ("J1", "Battery in (screw 5.08)", (-0.5, 0.4, 0.5, 3.6), [("+", 0, 1, "VBAT"), ("−", 0, 3, "GND")], "rect"),
    ("U2", "MCP1700-3302 TO-92", (1.5, 0.5, 4.5, 1.5), [("GND", 2, 1, "GND"), ("VIN", 3, 1, "VBAT"), ("VOUT", 4, 1, "3V3")], "rect"),
    ("C3", "10µF", (1.5, 2.5, 3.5, 3.5), [("−", 2, 3, "GND"), ("+", 3, 3, "VBAT")], "rect"),
    ("C1", "1000µF 6.3V", (6, 3, 1.9, None), [("+", 6, 2, "3V3"), ("−", 6, 4, "GND")], "circle"),
    ("C2", "100nF", (3.5, 4.5, 4.5, 6.5), [("+", 4, 5, "3V3"), ("−", 4, 6, "GND")], "rect"),
    ("R1", "1M", (0.5, 5.5, 1.5, 7.5), [("1", 1, 6, "VBAT"), ("2", 1, 7, "VSENSE")], "rect"),
    ("R2", "1M", (0.5, 7.5, 1.5, 9.5), [("1", 1, 8, "VSENSE"), ("2", 1, 9, "GND")], "rect"),
    ("C4", "100nF", (1.5, 7.5, 2.5, 9.5), [("1", 2, 8, "VSENSE"), ("2", 2, 9, "GND")], "rect"),
    ("J5", "1-Wire probes (screw ×3)", (5.5, 7.4, 6.5, 12.6), [("VDD", 6, 8, "S3V3"), ("DQ", 6, 10, "1W"), ("GND", 6, 12, "GND")], "rect"),
    ("R9", "4.7k", (3.5, 9.5, 5.5, 10.5), [("1", 4, 10, "S3V3"), ("2", 5, 10, "1W")], "rect"),
    ("INA", "INA219 module (socket)", (8.5, 0.6, 15.5, 8.4),
     [("VCC", 9, 2, "S3V3"), ("GND", 9, 3, "GND"), ("SCL", 9, 4, "SCL"), ("SDA", 9, 5, "SDA"),
      ("VIN−", 9, 6, "SHUNT_LO"), ("VIN+", 9, 7, "CELL+")], "rect"),
    ("Q1", "IRLB8721 TO-220", (16.5, 1.2, 19.5, 3.5), [("G", 17, 3, "SHORT"), ("D", 18, 3, "SHUNT_LO"), ("S", 19, 3, "GND")], "rect"),
    ("R3", "100k", (16.5, 4.5, 18.5, 5.5), [("1", 17, 5, "SHORT"), ("2", 18, 5, "GND")], "rect"),
    ("D1", "1N5819 (band →K)", (26.5, 1.5, 31.5, 2.5), [("K", 27, 2, "CHG_A"), ("A", 31, 2, "CELL+")], "rect"),
    ("Q2", "AO3401 on SOT-23 adapter", (22.5, 3.5, 25.5, 4.5), [("G", 23, 4, "Q2_G"), ("S", 24, 4, "CHG_A"), ("D", 25, 4, "CHG_IN")], "rect"),
    ("R5", "100k", (22.5, 5.5, 24.5, 6.5), [("1", 23, 6, "Q2_G"), ("2", 24, 6, "CHG_A")], "rect"),
    ("Q3", "2N7000 TO-92", (20.5, 7.5, 23.5, 8.5), [("S", 21, 8, "GND"), ("G", 22, 8, "CHG_EN"), ("D", 23, 8, "Q2_G")], "rect"),
    ("R6", "100k", (20.5, 9.5, 22.5, 10.5), [("1", 21, 10, "GND"), ("2", 22, 10, "CHG_EN")], "rect"),
    ("R4", "10k", (26.5, 5.5, 27.5, 7.5), [("1", 27, 6, "3V3"), ("2", 27, 7, "RAIL_EN")], "rect"),
    ("Q4", "AO3401 on SOT-23 adapter", (26.5, 7.5, 29.5, 8.5), [("G", 27, 8, "RAIL_EN"), ("S", 28, 8, "3V3"), ("D", 29, 8, "S3V3")], "rect"),
    ("R8", "100k", (29.5, 10.5, 31.5, 11.5), [("1", 30, 11, "3V3"), ("2", 31, 11, "CHG_STAT")], "rect"),
    ("J2", "Ref cell (screw 5.08)", (33.5, 1.4, 34.5, 4.6), [("+", 34, 2, "CELL+"), ("−", 34, 4, "GND")], "rect"),
    ("J3", "To CN3791 (screw ×3)", (33.5, 6.4, 34.5, 11.6), [("IN+", 34, 7, "CHG_IN"), ("IN−", 34, 9, "GND"), ("CHRG", 34, 11, "CHG_STAT")], "rect"),
    ("J6", "Button (screw)", (-0.5, 13.4, 0.5, 16.6), [("1", 0, 14, "BTN"), ("2", 0, 16, "GND")], "rect"),
    ("R7", "100k", (1.5, 13.5, 2.5, 15.5), [("1", 2, 14, "3V3"), ("2", 2, 15, "BTN")], "rect"),
    ("C5", "100nF", (2.5, 14.5, 3.5, 16.5), [("1", 3, 15, "BTN"), ("2", 3, 16, "GND")], "rect"),
    ("RTC", "DS3231 module (socket)", (-0.4, 19.4, 6.5, 25.6),
     [("32K", 6, 20, None), ("SQW", 6, 21, None), ("SCL", 6, 22, "SCL"), ("SDA", 6, 23, "SDA"),
      ("VCC", 6, 24, "S3V3"), ("GND", 6, 25, "GND")], "rect"),
]


def esp_part():
    pins = []
    for i, name in enumerate(ESP_TOP):
        c = 26 - i
        net = ESP_NETS.get(name, "GND" if name == "GND" else None)
        if name == "5V":
            net = "NC"
        pins.append((name, c, 14, net))
    for i, name in enumerate(ESP_BOT):
        c = 26 - i
        net = ESP_NETS.get(name)
        if name == "GND" and c == 26:
            net = "GND"
        pins.append((name, c, 24, net))
    return ("ESP32", "DevKitC 38-pin on female headers", (7.3, 13.2, 29.0, 24.8), pins, "rect")


NET_COLORS = {
    "GND": "#2b2f30", "VBAT": "#8a4b2a", "3V3": "#d23c2c", "S3V3": "#e8892b",
    "CELL+": "#7b4fb8", "SHUNT_LO": "#c24f9a", "CHG_A": "#1f8f8a", "Q2_G": "#5aa36a",
    "CHG_IN": "#127a9e", "CHG_EN": "#b59a12", "SHORT": "#9c6b00", "RAIL_EN": "#c15a5a",
    "CHG_STAT": "#5e7fd6", "VSENSE": "#7d8c2c", "BTN": "#a0522d", "SDA": "#2f6fd0",
    "SCL": "#1aa3c4", "1W": "#3e9b3e",
}
NET_INFO = {
    "GND": "Ground (all grounds common)",
    "VBAT": "Battery + (protected 18650)",
    "3V3": "3.3 V from U2 to ESP32 3V3 pin",
    "S3V3": "Switched sensor rail (Q4 drain)",
    "CELL+": "Reference cell +",
    "SHUNT_LO": "INA219 VIN− to Q1 drain",
    "CHG_A": "After D1, to Q2 source",
    "Q2_G": "Q2 gate (level-shifted by Q3)",
    "CHG_IN": "Q2 drain to CN3791 IN+",
    "CHG_EN": "GPIO27, high = charging allowed",
    "SHORT": "GPIO26, high = cell shorted for Isc",
    "RAIL_EN": "GPIO25, low = sensor rail on",
    "CHG_STAT": "GPIO34 ← CN3791 CHRG (open-drain)",
    "VSENSE": "GPIO35 ← battery divider",
    "BTN": "GPIO33 ← service button",
    "SDA": "I²C data, GPIO21",
    "SCL": "I²C clock, GPIO22",
    "1W": "1-Wire, GPIO4",
}


LABEL_POS = {
    "J1": (1.0, 2.0, "middle"), "U2": (3.0, 0.15, "middle"), "C3": (2.5, 4.2, "middle"),
    "C2": (4.6, 5.9, "start"), "R1": (0.0, 6.7, "middle"), "R2": (0.0, 8.7, "middle"),
    "C4": (3.0, 8.7, "start"), "J5": (7.0, 11.2, "middle"), "R9": (4.5, 9.2, "middle"),
    "Q4": (29.8, 8.2, "start"), "R4": (27.8, 6.7, "start"), "J6": (1.0, 15.2, "middle"),
    "R7": (2.0, 13.2, "middle"), "C5": (3.0, 17.2, "middle"), "J2": (33.2, 3.2, "end"),
    "J3": (33.2, 9.2, "end"),
}


def all_parts():
    return PARTS + [esp_part()]


def netlist() -> dict[str, list[dict]]:
    nets: dict[str, list[dict]] = {}
    for ref, _, _, pins, _ in all_parts():
        for name, c, r, net in pins:
            if net and net != "NC":
                nets.setdefault(net, []).append({"ref": ref, "pin": name, "hole": hole_name(c, r), "c": c, "r": r})
    return nets


def mst(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(points) < 2:
        return []
    inside = {0}
    edges = []
    while len(inside) < len(points):
        best = None
        for i in inside:
            for j in range(len(points)):
                if j in inside:
                    continue
                d = math.dist(points[i], points[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        edges.append((i, j))
        inside.add(j)
    return edges


def perfboard() -> str:
    p = 18
    ox, oy = 44, 34
    W, H = ox + COLS * p + 24, oy + ROWS * p + 22
    out = []
    X = lambda c: ox + c * p + p / 2  # noqa: E731
    Y = lambda r: oy + r * p + p / 2  # noqa: E731
    out.append(f'<rect class="board" x="{ox - 4}" y="{oy - 4}" width="{COLS * p + 8}" height="{ROWS * p + 8}" rx="6"/>')
    for c in range(COLS):
        if c % 5 == 4 or c == 0:
            out.append(f'<text class="axis" x="{X(c)}" y="{oy - 10}" text-anchor="middle">{c + 1}</text>')
    for r in range(ROWS):
        out.append(f'<text class="axis" x="{ox - 12}" y="{Y(r) + 3}" text-anchor="middle">{ROW_NAMES[r]}</text>')
        for c in range(COLS):
            out.append(f'<circle class="hole" cx="{X(c)}" cy="{Y(r)}" r="2"/>')
    # antenna keep-out
    out.append(f'<rect class="keep" x="{ox + 26.6 * p}" y="{oy + 13.2 * p}" width="{2.4 * p}" height="{11.6 * p}" rx="3"/>')
    out.append(f'<text class="axis" x="{ox + 27.8 * p}" y="{oy + 19 * p}" text-anchor="middle" '
               f'transform="rotate(90 {ox + 27.8 * p} {oy + 19 * p})">antenna · keep clear</text>')
    for ref, label, ol, pins, shape in all_parts():
        if shape == "circle":
            cc, cr, rad, _ = ol
            out.append(f'<circle class="fp" cx="{X(cc)}" cy="{Y(cr)}" r="{rad * p}"/>')
            out.append(f'<text class="fpl" x="{X(cc)}" y="{Y(cr) + 4}" text-anchor="middle">{ref}</text>')
        else:
            c0, r0, c1, r1 = ol
            out.append(f'<rect class="fp" x="{ox + c0 * p}" y="{oy + r0 * p}" width="{(c1 - c0) * p}" '
                       f'height="{(r1 - r0) * p}" rx="3"/>')
            if ref == "ESP32":
                out.append(f'<text class="fpl" x="{ox + 17.5 * p}" y="{oy + 18.6 * p}" text-anchor="middle">ESP32 DevKitC (USB ←)</text>')
                out.append(f'<text class="axis" x="{ox + 17.5 * p}" y="{oy + 19.6 * p}" text-anchor="middle">mounted on female headers, nothing underneath</text>')
            elif ref in ("INA", "RTC"):
                out.append(f'<text class="fpl" x="{ox + (c0 + c1) / 2 * p + 4}" y="{oy + (r0 + r1) / 2 * p}" text-anchor="middle">{"INA219" if ref == "INA" else "DS3231"}</text>')
                out.append(f'<text class="axis" x="{ox + (c0 + c1) / 2 * p + 4}" y="{oy + (r0 + r1) / 2 * p + 11}" text-anchor="middle">module on socket</text>')
            elif ref in LABEL_POS:
                lc, lr, anchor = LABEL_POS[ref]
                out.append(f'<text class="fpl" x="{X(lc)}" y="{Y(lr) + 3.5}" text-anchor="{anchor}">{ref}</text>')
            else:
                tx = ox + (c0 + c1) / 2 * p
                ty = oy + r0 * p - 3 if r0 > 0.6 else oy + r1 * p + 10
                if ref in ("J1", "J6"):
                    tx, ty = ox + c1 * p + 4, oy + (r0 + r1) / 2 * p + 3
                    out.append(f'<text class="fpl" x="{tx}" y="{ty}">{ref}</text>')
                    continue
                if ref in ("J2", "J3"):
                    tx, ty = ox + c0 * p - 4, oy + (r0 + r1) / 2 * p + 3
                    out.append(f'<text class="fpl" x="{tx}" y="{ty}" text-anchor="end">{ref}</text>')
                    continue
                if ref in ("R1", "R2", "C4", "J5", "R4", "C2", "R7", "C5"):
                    tx, ty = (ox + c1 * p + 3, oy + (r0 + r1) / 2 * p + 3)
                    anchor = "start"
                    if ref in ("R1", "R2"):
                        tx, anchor = ox + c0 * p - 3, "end"
                    if ref == "C4":
                        ty = oy + (r0 + r1) / 2 * p + 3
                    out.append(f'<text class="fpl" x="{tx}" y="{ty}" text-anchor="{anchor}">{ref}</text>')
                    continue
                out.append(f'<text class="fpl" x="{tx}" y="{ty}" text-anchor="middle">{ref}</text>')
    # ratsnest
    nets = netlist()
    for net, pins in nets.items():
        pts = [(X(q["c"]), Y(q["r"])) for q in pins]
        for i, j in mst(pts):
            (x1, y1), (x2, y2) = pts[i], pts[j]
            out.append(f'<line class="rat" data-net="{net}" stroke="{NET_COLORS[net]}" '
                       f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    # pins on top
    for ref, _, _, pins, _ in all_parts():
        for name, c, r, net in pins:
            fill = NET_COLORS.get(net, "#ffffff") if net and net != "NC" else "#ffffff"
            title = f"{ref} {name} · {hole_name(c, r)}" + (f" · {net}" if net else "")
            dn = f' data-net="{net}"' if net and net != "NC" else ""
            cls = "pin" if dn else "pin free"
            out.append(f'<circle class="{cls}"{dn} cx="{X(c)}" cy="{Y(r)}" r="4.6" fill="{fill}"><title>{title}</title></circle>')
            if net == "NC":
                out.append(f'<line class="nc" x1="{X(c) - 4}" y1="{Y(r) - 4}" x2="{X(c) + 4}" y2="{Y(r) + 4}"/>'
                           f'<line class="nc" x1="{X(c) - 4}" y1="{Y(r) + 4}" x2="{X(c) + 4}" y2="{Y(r) - 4}"/>')
    # ESP pin names for used pins
    for name, c, r, net in esp_part()[3]:
        if net and net != "NC" or name == "5V":
            # vertical labels inside the module outline, reading away from the header row
            x, y = X(c), Y(r) + (8 if r == 14 else -8)
            rot = 90 if r == 14 else -90
            out.append(f'<text class="axis pinname" x="{x}" y="{y}" dominant-baseline="middle" '
                       f'transform="rotate({rot} {x} {y})">{name}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Perfboard placement">{{STYLE}}{"".join(out)}</svg>'


def main() -> None:
    sch = schematic_full()
    (HERE / "schematic.svg").write_text(sch.render(STANDALONE_CSS))
    (HERE / "schematic.inline.svg").write_text(sch.render(None))
    pb = perfboard()
    (HERE / "perfboard.svg").write_text(pb.replace("{STYLE}", f"<style>{STANDALONE_CSS}</style>"))
    (HERE / "perfboard.inline.svg").write_text(pb.replace("{STYLE}", ""))
    nets = netlist()
    data = [{"net": n, "color": NET_COLORS[n], "info": NET_INFO[n],
             "pins": [{k: q[k] for k in ("ref", "pin", "hole")} for q in pins]} for n, pins in nets.items()]
    order = list(NET_INFO)
    data.sort(key=lambda d: order.index(d["net"]))
    (HERE / "netlist.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(f"wrote schematic.svg, perfboard.svg, netlist.json ({len(data)} nets)")


if __name__ == "__main__":
    main()

