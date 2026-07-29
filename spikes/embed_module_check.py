# -*- coding: utf-8 -*-
r"""제품 코드(hwp_palette.hwp.hwp_embed)가 실제로 임베드되는지 자동 확인.

전용 한글 인스턴스(DispatchEx)를 새로 띄워 그 창만 쓴다 — 열어 둔 문서는
건드리지 않는다. 순서: 띄우기 → Embed.start → COM 검사 → stop → 살아있나.

    python spikes\embed_module_check.py
"""

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32con
import win32gui
import win32process
import win32com.client

from hwp_palette.hwp import hwp_embed

OUT = []


def log(m):
    OUT.append(m)
    print(m, flush=True)


def hwp_wins(pid):
    found = []

    def cb(h, _):
        try:
            if "hwp.exe" in win32gui.GetClassName(h).lower():
                if win32process.GetWindowThreadProcessId(h)[1] == pid:
                    found.append(h)
        except Exception:
            pass

    win32gui.EnumWindows(cb, None)
    return found


def pids():
    out = set()

    def cb(h, _):
        try:
            if "hwp.exe" in win32gui.GetClassName(h).lower():
                out.add(win32process.GetWindowThreadProcessId(h)[1])
        except Exception:
            pass

    win32gui.EnumWindows(cb, None)
    return out


root = tk.Tk()
root.title("hwp_embed 자동 확인")
root.geometry("900x640")
host = tk.Frame(root, bg="#d0d7de")
host.pack(fill="both", expand=True, padx=6, pady=6)
root.update()

before = pids()
hwp = win32com.client.DispatchEx("HWPFrame.HwpObject")
try:
    hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
except Exception as e:
    log(f"보안모듈 등록 실패(무시): {e}")
hwp.XHwpWindows.Item(0).Visible = True

hwnd = pid = None
for _ in range(50):
    new = pids() - before
    if new:
        pid = next(iter(new))
        w = hwp_wins(pid)
        if w:
            hwnd = w[0]
            break
    root.update()
    time.sleep(0.1)

if not hwnd:
    log("✗ 전용 한글 창을 못 찾음 — 중단")
    root.destroy()
    sys.exit(1)
log(f"전용 한글 pid={pid} hwnd={hwnd}")

emb = hwp_embed.Embed(root, host, hwnd)
ok = emb.start()
root.update()
time.sleep(0.6)
root.update()
parent = win32gui.GetParent(hwnd)
log(f"start()={ok} GetParent={parent} host={host.winfo_id()} "
    f"→ {'✓ 판 안에 들어갔다' if parent == host.winfo_id() else '✗ 아니다'}")
l, t, r, b = win32gui.GetWindowRect(hwnd)
hl, ht, hr, hb = win32gui.GetWindowRect(host.winfo_id())
log(f"크기: 한글={r - l}x{b - t} 판={hr - hl}x{hb - ht}")

# 창을 키워 본다 — <Configure> 로 자식이 따라 커지는가
root.geometry("1100x760")
root.update()
time.sleep(0.5)
root.update()
l, t, r, b = win32gui.GetWindowRect(hwnd)
hl, ht, hr, hb = win32gui.GetWindowRect(host.winfo_id())
log(f"창 키운 뒤: 한글={r - l}x{b - t} 판={hr - hl}x{hb - ht} "
    f"→ {'✓ 따라 커짐' if (r - l, b - t) == (hr - hl, hb - ht) else '✗ 어긋남'}")

try:
    t0 = time.time()
    hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet)
    hwp.HParameterSet.HInsertText.Text = "임베드 중 COM 검사"
    hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet)
    log(f"✓ 임베드 중 COM InsertText ({time.time() - t0:.2f}s)")
except Exception as e:
    log(f"✗ 임베드 중 COM 실패: {e}")

emb.stop()
root.update()
time.sleep(0.6)
alive = bool(win32gui.IsWindow(hwnd))
parent = win32gui.GetParent(hwnd) if alive else None
style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE) if alive else 0
log(f"stop() 뒤: 창살아있음={alive} GetParent={parent} "
    f"WS_CHILD={'있음(✗)' if style & win32con.WS_CHILD else '없음(✓)'} "
    f"WS_CAPTION={'있음(✓)' if style & win32con.WS_CAPTION else '없음(✗)'}")
try:
    hwp.HAction.Run("Cancel")
    log("✓ 해제 뒤에도 COM 살아 있음")
except Exception as e:
    log(f"✗ 해제 뒤 COM: {e}")

try:
    hwp.XHwpDocuments.Item(0).Clear(1)     # 저장 묻지 않고 버린다
except Exception:
    pass
try:
    hwp.Quit()
except Exception:
    pass
root.destroy()
print("\n".join(OUT))
