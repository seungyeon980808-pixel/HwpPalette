# -*- coding: utf-8 -*-
r"""임베드(SetParent) 중 **한글이 정말 글을 받아 쓰는가** 실측 (2026-07-30).

임베드의 최대 위험은 겉모습이 아니라 입력이다. 프로세스가 다른 창을 자식으로
넣으면 **키보드 초점이 부모 스레드로 가버려 자식이 타자를 못 받는** 경우가
있다 (윈도우의 입력 큐는 창이 아니라 스레드에 붙어 있기 때문). 눈으로는
멀쩡해 보이는데 글자만 안 들어가는 상태가 되므로, 사람 대신 기계가 확인한다.

재는 것:
  1) 임베드한 뒤 한글 편집창을 클릭하면 초점이 거기로 가는가
  2) **실제 키보드 입력**(SendInput)이 문서에 들어가는가 ← 핵심
  3) 그 문서를 파일로 저장하면 멀쩡한 hwp 가 나오는가
  4) 임베드를 풀고 나서도 한글이 살아 있는가

실행: python spikes/embed_input_spike.py
"""

import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
import win32api
import win32con
import win32gui
import win32process

from hwp_palette.hwp import hwp_engine, hwp_embed

DOCK_W, DOCK_H = 1180, 900
MARK = "EMBEDTEST9137"          # 문서에서 찾아낼 표식 (한글이 안 바꿀 아스키)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   f"_embed_spike_out_{os.getpid()}.hwp")   # 한글이 붙들고
# 있으면 다음 실행이 못 지운다 — 실행마다 다른 이름을 쓴다.

# 대조군 (--no-embed): 임베드하지 않고 똑같은 순서로 잰다. IME 결과가
# 임베드 탓인지, 합성 한/영 키가 원래 안 먹는 것인지 가르는 유일한 방법이다.
NO_EMBED = "--no-embed" in sys.argv

result = {}


def say(step, ok, detail=""):
    mark = "OK  " if ok else "FAIL"
    result[step] = ok
    print(f"  [{mark}] {step}" + (f" — {detail}" if detail else ""))


def focus_owner(hwnd):
    """그 창의 스레드가 쥔 키보드 초점 창."""
    me = win32api.GetCurrentThreadId()
    tid, _ = win32process.GetWindowThreadProcessId(hwnd)
    win32process.AttachThreadInput(me, tid, True)
    try:
        return win32gui.GetFocus()
    finally:
        win32process.AttachThreadInput(me, tid, False)


def click(x, y):
    win32api.SetCursorPos((x, y))
    time.sleep(0.15)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.3)


def type_ascii(text):
    """실제 키보드로 친다 (COM 삽입이 아니다 — 그건 초점과 무관하게 되므로)."""
    for ch in text:
        vk = win32api.VkKeyScan(ch)
        code = vk & 0xFF
        shift = bool(vk & 0x100)
        if shift:
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
        win32api.keybd_event(code, 0, 0, 0)
        win32api.keybd_event(code, 0, win32con.KEYEVENTF_KEYUP, 0)
        if shift:
            win32api.keybd_event(win32con.VK_SHIFT, 0,
                                 win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)
    time.sleep(0.5)


# COM 은 **주 스레드에서만** 부른다 (실측 2026-07-30): 연결 객체를 만든
# 스레드가 아닌 곳에서 쓰면 "CoInitialize가 호출되지 않았습니다"로 죽는다.
# 작업 스레드는 Tk 의 after 로 일을 주 스레드에 넘기고 결과를 기다린다.
_ui = {"root": None}


def on_main(fn, timeout=10.0):
    """주 스레드에서 fn() 을 돌리고 결과를 받아온다."""
    done = threading.Event()
    box = {}

    def run():
        try:
            box["v"] = fn()
        except Exception as e:
            box["e"] = e
        finally:
            done.set()

    _ui["root"].after(0, run)
    if not done.wait(timeout):
        raise TimeoutError("주 스레드 응답 없음")
    if "e" in box:
        raise box["e"]
    return box.get("v")


def doc_text():
    try:
        return on_main(lambda: hwp_engine.hwp.GetTextFile("TEXT", "") or "")
    except Exception as e:
        return f"<읽기 실패 {e}>"


def main():
    print("한글 연결 중...")
    hwp_engine.connect()
    hwp_engine.new_document()
    hwp_engine.ensure_visible()
    hwnd = hwp_engine.connected_hwnd()
    print("한글 창 =", hwnd)

    root = tk.Tk()
    _ui["root"] = root
    root.title("임베드 입력 스파이크")
    root.attributes("-topmost", False)         # 앱의 임베드 중 동작과 같게
    root.geometry(f"{DOCK_W}x{DOCK_H}+40+40")
    tk.Label(root, text="임베드 입력 실측 — 건드리지 마세요",
             font=("맑은 고딕", 10)).pack(fill="x", pady=6)
    host = tk.Frame(root, bg="#dddddd")
    host.pack(fill="both", expand=True, padx=6, pady=(4, 6))
    root.update_idletasks()
    root.update()

    if NO_EMBED:
        emb = None
        print("\n*** 대조군: 임베드하지 않고 잰다 ***\n")
        try:                        # 한글을 앞으로 (평소처럼 독립 창)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(0.5)
    else:
        emb = hwp_embed.Embed(root, host, hwnd)
        started = emb.start()
        print(f"\n임베드 시작 = {started}\n")
        if not started:
            return

    def worker():
        time.sleep(1.5)
        try:
            say("임베드 후에도 한글 창이 살아 있다",
                bool(win32gui.IsWindow(hwnd)))
            if not NO_EMBED:
                parent = win32gui.GetParent(hwnd)
                say("한글이 우리 판의 자식이 되었다", parent == host.winfo_id(),
                    f"parent={parent} host={host.winfo_id()}")
                # 우리 창을 앞으로 (사용자가 쓰는 상황과 같게)
                try:
                    win32gui.SetForegroundWindow(root.winfo_id())
                except Exception:
                    pass
                time.sleep(0.4)

            l, t, r, b = win32gui.GetWindowRect(hwnd)
            # 편집 영역은 창 아래쪽 — 리본·눈금자를 피해 한복판보다 살짝 아래
            x, y = (l + r) // 2, t + int((b - t) * 0.55)
            print(f"  (클릭 지점 {x},{y} / 한글 rect {l},{t},{r},{b})")
            click(x, y)

            hit = win32gui.WindowFromPoint((x, y))
            # 그 창에서 부모를 타고 올라가며 한글 창을 만나는지 본다
            chain, p, in_hwp = [], hit, False
            while p and len(chain) < 8:
                chain.append(f"{win32gui.GetClassName(p)}({p})")
                if p == hwnd:
                    in_hwp = True
                    break
                p = win32gui.GetParent(p)
            say("클릭이 한글에게 간다", in_hwp, " → ".join(chain))
            say("한글 스레드가 키보드 초점을 쥐고 있다",
                bool(focus_owner(hwnd)), f"focus={focus_owner(hwnd)}")

            before = doc_text()
            type_ascii(MARK)
            after = doc_text()
            say("실제 키보드 타자가 문서에 들어간다", MARK in after,
                f"문서 = {after.strip()[:60]!r}")

            # ── 한글(IME) 조합 — 임베드의 진짜 위험 지점 ──
            # 프로세스가 다른 자식 창은 IME 문맥(HIMC)이 부모 스레드에 묶여
            # 조합이 깨지는 경우가 있다. 영문만 되고 한글이 안 되면 이 도구는
            # 쓸모가 없으므로 반드시 잰다.
            try:
                win32api.keybd_event(0x15, 0, 0, 0)            # VK_HANGUL
                win32api.keybd_event(0x15, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.4)
                type_ascii("gksrmf")        # 두벌식 → '한글'
                win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)   # 조합 확정
                win32api.keybd_event(win32con.VK_RETURN, 0,
                                     win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.6)
                ko = doc_text()
                say("한글(IME) 조합이 문서에 들어간다", "한글" in ko,
                    f"문서 = {ko.strip()[:60]!r}")
            except Exception as e:
                say("한글(IME) 조합이 문서에 들어간다", False, str(e))
            finally:
                win32api.keybd_event(0x15, 0, 0, 0)            # 영문으로 되돌림
                win32api.keybd_event(0x15, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.2)

            if MARK in after:
                try:
                    if os.path.exists(OUT):
                        os.remove(OUT)
                    on_main(lambda: hwp_engine.hwp.save_as(OUT, format="HWP"))
                    time.sleep(0.8)
                    size = os.path.getsize(OUT) if os.path.exists(OUT) else 0
                    say("파일로 저장되고 내용이 들어 있다", size > 1000,
                        f"{OUT} ({size} bytes)")
                except Exception as e:
                    say("파일로 저장되고 내용이 들어 있다", False, str(e))
            else:
                say("파일로 저장되고 내용이 들어 있다", False, "타자가 안 들어가 건너뜀")
        except Exception as e:
            print("  측정 중 예외:", e)

        print("\n임베드 해제 중...")
        try:
            if emb is not None:
                emb.stop()
            time.sleep(0.6)
            say("해제 뒤에도 한글이 살아 있다", bool(win32gui.IsWindow(hwnd)))
            say("해제 뒤 한글이 독립 창으로 돌아왔다" if not NO_EMBED
                else "(대조군) 한글이 독립 창이다",
                win32gui.GetParent(hwnd) in (0, None),
                f"parent={win32gui.GetParent(hwnd)}")
        except Exception as e:
            print("  해제 중 예외:", e)

        print("\n=== 요약 ===")
        for k, v in result.items():
            print(f"  {'OK  ' if v else 'FAIL'} {k}")
        print("\n판정:", "임베드에서 글이 써진다" if result.get(
            "실제 키보드 타자가 문서에 들어간다") else "임베드에서 글이 안 써진다")
        try:
            root.after(0, root.destroy)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    main()
