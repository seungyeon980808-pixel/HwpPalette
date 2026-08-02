# -*- coding: utf-8 -*-
r"""041 검증 — Dock 클래스가 실제 한글에 **위계로** 붙고 깨끗이 떨어지는가.

스파이크는 Win32 원시 호출만 쟀다. 여기서는 진짜 Dock 을 써서 본다:
  · 위계로 붙었는가 (_owner_set), 구멍은 안 뚫었는가 (_hole is None)
  · 우리 창을 '항상 위'로 올려도 한글이 판 자리에 남는가 (④)
  · 뗀 뒤 소유자·구멍·자리가 모두 원복되는가

한글 문서는 열지도 만들지도 않는다.
"""
import ctypes, io, pathlib, sys, time, tkinter as tk
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import win32con, win32gui
from hwp_palette.hwp import hwp_dock, hwp_engine

out=[]
def say(*a): out.append(" ".join(str(x) for x in a))
u=ctypes.windll.user32
GWLP=-8
u.GetWindowLongPtrW.restype=ctypes.c_void_p
u.GetWindowLongPtrW.argtypes=(ctypes.c_void_p,ctypes.c_int)

def at(x,y):
    h=u.WindowFromPoint(ctypes.wintypes.POINT(int(x),int(y)))
    return win32gui.GetAncestor(h,2) if h else 0

try:
    hwp_engine.connect(); hwp_engine.ensure_visible()
    hwnd=hwp_engine.connected_hwnd()
    if win32gui.IsIconic(hwnd):          # 최소화돼 있으면 먼저 편다
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE); time0=0
    rect0=win32gui.GetWindowRect(hwnd)
    say(f"한글 hwnd={hwnd} 원래자리={rect0}")

    root=tk.Tk(); root.title("도킹 검증"); root.geometry("980x680+100+80")
    tk.Label(root,text="도구줄",bg="#dfe6ee").pack(fill="x",ipady=8)
    pane=tk.Frame(root,bg="#ffe0e0"); pane.pack(fill="both",expand=True)
    root.update()
    ours=win32gui.GetAncestor(pane.winfo_id(),2)

    d=hwp_dock.Dock(root, pane, hwnd)
    ok=d.start(); root.update()
    say(f"\nstart()={ok}")
    say(f"  위계로 붙었나 _owner_set={d._owner_set}")
    say(f"  구멍 안 뚫었나 _hole={d._hole}  ← None 이면 안 뚫음(③ 해결)")
    say(f"  한글의 소유자={u.GetWindowLongPtrW(hwnd,GWLP)} (우리 창={ours})")
    say(f"  대장에 위계 보고: {hwp_dock.owner_has_hierarchy() if hwp_dock.owner() else '(대장 미사용)'}")

    time.sleep(0.6); root.update()
    cx=pane.winfo_rootx()+pane.winfo_width()//2
    cy=pane.winfo_rooty()+pane.winfo_height()//2
    say(f"  판 가운데에 보이는 것 = {'한글' if at(cx,cy)==hwnd else ('우리 창' if at(cx,cy)==ours else '남의 창')}")

    # ④ 항상 위
    root.attributes("-topmost",True); root.update()
    d.keep_order(force=True)          # 앱의 _toggle_top 이 하는 일 (reorder_now)
    root.update(); time.sleep(0.5); root.update()
    who=at(cx,cy)
    say(f"\n[④] 우리 창을 '항상 위'로 올린 뒤")
    say(f"  판 가운데 = {'한글' if who==hwnd else ('우리 창' if who==ours else '남의 창')}"
        "   ← '한글' 이면 도킹 중 항상 위가 된다")
    root.attributes("-topmost",False); d.keep_order(force=True); root.update()

    d.stop(); root.update(); time.sleep(0.4)
    say(f"\nstop() 뒤")
    say(f"  소유자={u.GetWindowLongPtrW(hwnd,GWLP)}  ← 0 이어야 깨끗")
    say(f"  _owner_set={d._owner_set} _hole={d._hole}")
    say(f"  한글 자리={win32gui.GetWindowRect(hwnd)}")
    say(f"  원래자리와 같나={win32gui.GetWindowRect(hwnd)==rect0}")
    root.destroy()
except Exception as e:
    import traceback; say("예외:",type(e).__name__,e); say(traceback.format_exc())
io.open(pathlib.Path(__file__).with_suffix(".log"),"w",encoding="utf-8").write("\n".join(out))
print("done")
