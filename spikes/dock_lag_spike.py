# -*- coding: utf-8 -*-
r"""도킹 추적 지연 실측 — 옛 방식(폴링+완화) vs 새 방식(이벤트 훅+스냅) (2026-07-30).

사용자 지시: "수단과 방법을 가리지 말고 도킹한 창의 버벅임을 최소화하라."
버벅임의 정체는 **추적 지연**이다 — 우리 창이 움직인 순간과 한글이 따라온
순간의 시간차가 곧 '창 둘이 따로 노는' 화면이 된다. 그래서 고치기 전에 재고,
고친 뒤에 다시 재서 숫자로 비교한다.

재는 것 (창을 프로그램으로 40번 끌며):
  · 매 걸음 직후의 어긋남(px) — 평균/최대
  · 300px 점프 후 완전히 붙을 때까지 걸린 시간(ms)

실행: python spikes/dock_lag_spike.py   (한글 창이 잠깐 떴다 움직인다)
"""

import os
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
import win32con
import win32gui

from hwp_palette.hwp import hwp_engine, hwp_dock

W, H = 900, 700
STEPS = 40          # 끌기 걸음 수
STEP_PX = 14        # 한 걸음 크기 — 실제 드래그의 프레임당 이동량 수준
STEP_S = 0.012      # 걸음 간격 — 80~90fps 드래그를 흉내


class OldFollower:
    """옛 추적 방식 재현 — 30ms 폴링 + 완화 45% (비교 기준)."""

    TICK, EASE, SNAP = 0.03, 0.45, 2

    def __init__(self, host_hwnd, hwnd):
        self.host_hwnd, self.hwnd = host_hwnd, hwnd
        self._stop = threading.Event()
        self._t = None

    def start(self):
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return True

    def _loop(self):
        flags = (win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE
                 | win32con.SWP_NOZORDER)
        while not self._stop.is_set():
            try:
                l, t, r, b = win32gui.GetWindowRect(self.host_hwnd)
                tw, th = max(r - l, 200), max(b - t, 200)
                cl, ct, cr, cb = win32gui.GetWindowRect(self.hwnd)
                cw, ch = cr - cl, cb - ct
                dl, dt, dw, dh = l - cl, t - ct, tw - cw, th - ch
                if all(abs(v) <= self.SNAP for v in (dl, dt, dw, dh)):
                    if (dl, dt, dw, dh) != (0, 0, 0, 0):
                        win32gui.SetWindowPos(self.hwnd, 0, l, t, tw, th, flags)
                    time.sleep(0.05)
                    continue
                win32gui.SetWindowPos(
                    self.hwnd, 0,
                    cl + int(dl * self.EASE), ct + int(dt * self.EASE),
                    cw + int(dw * self.EASE), ch + int(dh * self.EASE), flags)
            except Exception:
                pass
            time.sleep(self.TICK)

    def stop_follow(self):
        self._stop.set()
        if self._t:
            self._t.join(timeout=0.5)

    def stop(self):
        self.stop_follow()


def lag_px(host_hwnd, hwnd):
    l, t, _r, _b = win32gui.GetWindowRect(host_hwnd)
    cl, ct, _cr, _cb = win32gui.GetWindowRect(hwnd)
    return max(abs(l - cl), abs(t - ct))


def drag_run(root_hwnd, host_hwnd, hwnd):
    """창을 지그재그로 끌며 걸음마다 어긋남을 잰다."""
    lags = []
    x, y = win32gui.GetWindowRect(root_hwnd)[:2]
    for i in range(STEPS):
        dx = STEP_PX if (i // 10) % 2 == 0 else -STEP_PX
        x += dx
        y += STEP_PX if i % 2 else -STEP_PX
        win32gui.SetWindowPos(root_hwnd, 0, x, y, 0, 0,
                              win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                              | win32con.SWP_NOACTIVATE)
        time.sleep(STEP_S)
        lags.append(lag_px(host_hwnd, hwnd))
    return lags


def settle_run(root_hwnd, host_hwnd, hwnd):
    """300px 점프 후 완전히(±2px) 붙을 때까지 몇 ms 걸리나."""
    l, t = win32gui.GetWindowRect(root_hwnd)[:2]
    win32gui.SetWindowPos(root_hwnd, 0, l + 300, t, 0, 0,
                          win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                          | win32con.SWP_NOACTIVATE)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 2.0:
        if lag_px(host_hwnd, hwnd) <= 2:
            return (time.perf_counter() - t0) * 1000
        time.sleep(0.002)
    return 2000.0


def measure(name, follower, root, root_hwnd, host_hwnd, hwnd):
    ok = follower.start()
    print(f"\n── {name} (시작={ok}) ──")
    time.sleep(0.8)                      # 정착 대기
    lags = drag_run(root_hwnd, host_hwnd, hwnd)
    settle = settle_run(root_hwnd, host_hwnd, hwnd)
    follower.stop_follow()
    print(f"  끌기 중 어긋남: 평균 {statistics.mean(lags):5.1f}px"
          f" / 최대 {max(lags)}px")
    print(f"  300px 점프 후 정착: {settle:6.1f}ms")
    return statistics.mean(lags), max(lags), settle


def main():
    print("한글 연결 중...")
    hwp_engine.connect()
    hwp_engine.new_document()
    hwp_engine.ensure_visible()
    hwnd = hwp_engine.connected_hwnd()

    root = tk.Tk()
    root.title("도킹 지연 실측")
    root.geometry(f"{W}x{H}+80+80")
    host = tk.Frame(root, bg="#dddddd")
    host.pack(fill="both", expand=True, padx=6, pady=6)
    root.update_idletasks()
    root.update()
    root_hwnd = win32gui.GetAncestor(host.winfo_id(), win32con.GA_ROOT)
    host_hwnd = host.winfo_id()

    results = {}

    def worker():
        try:
            results["old"] = measure(
                "옛 방식 — 30ms 폴링 + 완화 45%",
                OldFollower(host_hwnd, hwnd),
                root, root_hwnd, host_hwnd, hwnd)
            time.sleep(0.5)
            results["new"] = measure(
                "새 방식 — 이벤트 훅 + 즉시 스냅",
                hwp_dock.Dock(root, host, hwnd),
                root, root_hwnd, host_hwnd, hwnd)
            o, n = results["old"], results["new"]
            print("\n=== 비교 ===")
            print(f"  평균 어긋남  {o[0]:6.1f}px → {n[0]:6.1f}px")
            print(f"  최대 어긋남  {o[1]:6d}px → {n[1]:6d}px")
            print(f"  정착 시간    {o[2]:6.1f}ms → {n[2]:6.1f}ms")
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            try:
                root.after(0, root.destroy)
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    main()
