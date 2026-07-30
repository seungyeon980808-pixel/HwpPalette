# -*- coding: utf-8 -*-
r"""따라오기가 얼마나 부드러운지 **수치로** 잰다 (2026-07-30, 사용자 요청
"더 부드럽게 도킹된 화면이 따라올 수 있도록 검증을 통해서 확인").

전용 한글을 띄워 도킹한 뒤, 우리 창을 60프레임 동안 끌 듯이 조금씩 옮기며
매 프레임 직후 한글이 판에서 몇 px 떨어져 있는지 잰다. 이벤트 훅이 즉시
스냅한다면 어긋남은 다음 측정 전에 이미 0 이어야 한다.

기준: 평균 어긋남 5px 이하 + 마지막 정착 30ms 이내면 합격.
"""

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32con
import win32gui

from hwp_palette.hwp import hwp_dock
from dock_fix_spike import spawn, doc_windows, log


def main():
    com, pid = spawn()
    if not pid:
        log("✗ 전용 한글을 못 띄웠다")
        return
    hwnd = doc_windows(pid)[0][0]

    root = tk.Tk()
    root.title("부드러움 스파이크")
    root.geometry("900x700+150+120")
    host = tk.Frame(root, bg="#dddddd")
    host.pack(fill="both", expand=True, padx=10, pady=10)
    root.update()

    dock = hwp_dock.Dock(root, host, hwnd)
    log(f"start() → {dock.start()}")
    root.update()
    time.sleep(0.8)

    def offset():
        hl, ht, hr, hb = win32gui.GetWindowRect(host.winfo_id())
        cl, ct, cr, cb = win32gui.GetWindowRect(hwnd)
        return abs(cl - hl) + abs(ct - ht)

    def measure(tag, frame_s):
        """60프레임 끌기 흉내 — 프레임마다 6px 씩 옮기고 어긋남을 잰다."""
        offs = []
        x, y = root.winfo_x(), root.winfo_y()
        for i in range(60):
            x += 6 if i < 30 else -6
            y += 4 if i % 2 else -2
            root.geometry(f"+{x}+{y}")
            root.update()
            time.sleep(frame_s)
            offs.append(offset())
        t0 = time.time()
        settle = None
        while time.time() - t0 < 1.0:
            if offset() == 0:
                settle = (time.time() - t0) * 1000
                break
            time.sleep(0.002)
        avg = sum(offs) / len(offs)
        log(f"{tag}: 평균 어긋남 {avg:.1f}px · 최대 {max(offs)}px · "
            f"0px 프레임 {sum(1 for o in offs if o == 0)}/60 · "
            f"정착 {settle:.1f}ms" if settle is not None else
            f"{tag}: 평균 {avg:.1f}px · 최대 {max(offs)}px · 정착 1초 초과 ✗")
        return avg, settle

    avg60, settle = measure("60fps 끌기(16ms)", 0.016)
    avg120, _ = measure("빠른 끌기(8ms)", 0.008)

    verdict = ("합격 ✓" if avg60 <= 5 and (settle or 999) <= 30 else "불합격 ✗")
    log(f"판정: {verdict} (기준: 평균 5px 이하 + 정착 30ms 이내)")

    dock.stop()
    root.update()
    root.destroy()
    try:
        com.XHwpDocuments.Item(0).Clear(1)
        com.Quit()
    except Exception as e:
        log(f"정리 실패(수동으로 닫을 것): {e}")


if __name__ == "__main__":
    main()
