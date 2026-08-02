# -*- coding: utf-8 -*-
r"""전 화면 훑기 — 모든 창을 하나씩 열어 보고 실사용 문제를 찾는다 (2026-08-02).

사용자 지시: *"이 프로그램에 있는 모든 기능을 하나씩 다 써보면서 어떤
문제점이 있는지 확인해봐. 실사용자 입장에서."*

화면을 직접 누를 권한이 없으므로 **코드로 같은 창을 띄우고** 안을 들여다본다.
사람 눈 대신 재는 것들:
  · 창이 뜨다가 터지는가        → 사용자에게는 "눌렀는데 아무 일이 없다"
  · 창이 **멈춰 서는가**        → 모달 대기. 다른 창을 못 만진다
  · 화면 밖으로 나가거나 화면보다 큰가 → 아래쪽 단추에 손이 안 닿는다
  · Escape 로 닫히는가          → 되돌아 나오는 길
  · 빈 상태에서 무엇을 하라고 말해 주는가

⚠ 창 하나가 멈춰도 나머지를 계속 보려면 **각각 따로 띄워야** 한다 —
이 파일은 인자로 받은 화면 하나만 열고, 아래 run_all 이 하나씩 프로세스로
돌리며 시간 제한을 건다.

한글은 건드리지 않는다.
"""

import io
import os
import pathlib
import subprocess
import sys
import tkinter as tk
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOG = pathlib.Path(__file__).with_suffix(".log")
TIMEOUT_S = 40


# ── 열어 볼 화면들 (이름, 만드는 코드) ──────────────────
SCREENS = {
    "물감설정": "library_ui.open_manager(root)",
    "팔레트설정": "palette_ui.open_settings(root)",
    "도움말": "help_ui.open_help(root)",
    "양식채우기": "form_fill_ui.open_form_fill(root)",
    "문항엑셀": "excel_ui.open_excel(root)",
    "꾸러미만들기": "mix_ui.open_mix_dialog(root)",
    "특수기호고르기": "palette_ui._CharDialog(root)",
    "블럭종류고르기": "palette_ui._BlockKindDialog(root, (1, 1))",
    "물감이름": 'library_ui.MetaDialog(root, "서식", {})',
    "온보딩": "onboarding.Onboarding(root, lambda *a: ('맑은 고딕', 10))",
    "튜토리얼고르기": "tutorial.open_picker(root, [])",
}


def _one(name):
    """화면 하나만 열고 살핀 뒤 결과를 stdout 으로 뱉는다."""
    out = []

    def say(*a):
        out.append(" ".join(str(x) for x in a))

    try:
        from hwp_palette.ui import (excel_ui, form_fill_ui, help_ui,
                                    library_ui, mix_ui, onboarding,
                                    palette_ui, tutorial)
        root = tk.Tk()
        # eval 은 중첩 함수의 지역 이름을 못 본다 — 이름공간을 직접 넘긴다
        ns = {"excel_ui": excel_ui, "form_fill_ui": form_fill_ui,
              "help_ui": help_ui, "library_ui": library_ui, "mix_ui": mix_ui,
              "onboarding": onboarding, "palette_ui": palette_ui,
              "tutorial": tutorial, "root": root}
        root.geometry("400x300+60+60")
        root.update()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()

        # 모달 대기를 깨는 안전장치 — 창이 wait_window 로 잠기면 여기서 푼다
        state = {"win": None}

        def look():
            win = state["win"]
            if win is None or not win.winfo_exists():
                return
            try:
                win.update_idletasks()
                w, h = win.winfo_width(), win.winfo_height()
                x, y = win.winfo_rootx(), win.winfo_rooty()
                say(f"SIZE {w}x{h} @({x},{y}) 화면 {sw}x{sh}")
                if w > sw or h > sh:
                    say(f"FIND 높음 창이 화면보다 크다 ({w}x{h} > {sw}x{sh})"
                        " — 아래쪽 단추에 손이 안 닿는다")
                if x < -50 or y < -50 or x > sw - 100 or y > sh - 60:
                    say(f"FIND 높음 창이 화면 밖에 선다 @({x},{y})"
                        " — 못 찾거나 못 끈다")
                if "Escape" not in str(win.bind()):
                    say("FIND 보통 Escape 로 닫히지 않는다"
                        " — 되돌아 나오는 길이 마우스뿐")
                try:
                    if win.grab_current() is win:
                        say("MODAL 이 창이 마우스를 잡고 있다(모달)")
                except Exception:
                    pass
            except Exception as e:
                say(f"FIND 높음 연 뒤 살피다 터짐: {type(e).__name__}: {e}")
            finally:
                try:
                    win.grab_release()
                except Exception:
                    pass
                try:
                    win.destroy()
                except Exception:
                    pass
                root.after(200, root.quit)

        def start():
            try:
                state["win"] = eval(SCREENS[name], ns)   # noqa: S307 — 우리 목록뿐
            except Exception as e:
                say(f"FIND 치명 창이 열리다 터진다 ({type(e).__name__}: {e})"
                    " — 사용자에게는 '눌렀는데 아무 일도 안 일어남'")
                say("TRACE " + traceback.format_exc().splitlines()[-1])
                root.after(50, root.quit)
                return
            root.after(700, look)

        root.after(60, start)
        root.mainloop()
        try:
            root.destroy()
        except Exception:
            pass
    except Exception as e:
        say(f"FIND 치명 화면을 준비하다 터짐: {type(e).__name__}: {e}")
    print("\n".join(out))


def run_all():
    lines, findings = [], []

    def say(*a):
        lines.append(" ".join(str(x) for x in a))

    from hwp_palette.model import library, palette
    counts = {c: len(library.list_items(c))
              for c in ("서식", "문자", "템플릿", "양식", "사진")}
    tabs = palette.load_tabs()
    say(f"창고 현황: {counts}")
    say(f"팔레트 탭 {len(tabs)}개 · 첫 탭 블럭 "
        f"{len(tabs[0].get('blocks', [])) if tabs else 0}개")

    for name in SCREENS:
        say(f"\n── {name}")
        try:
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            p = subprocess.run([sys.executable, __file__, "--one", name],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               env=env, timeout=TIMEOUT_S)
            if p.returncode and not (p.stdout or "").strip():
                say(f"    ✗ 하위 프로세스가 죽었다 (exit {p.returncode})")
                tail = (p.stderr or "").strip().splitlines()[-1:] or [""]
                findings.append(("치명", name, f"열다 죽는다: {tail[0][:160]}"))
            body = (p.stdout or "").strip()
        except subprocess.TimeoutExpired:
            say(f"    ⏱ {TIMEOUT_S}초 안에 안 끝났다")
            findings.append(("높음", name,
                             "창이 멈춰 선다(모달 대기) — 열려 있는 동안 "
                             "다른 창을 못 만진다. 실수로 뒤에 숨으면 "
                             "프로그램이 통째로 굳은 것처럼 보인다"))
            continue
        for ln in body.splitlines():
            if ln.startswith("FIND "):
                _, lv, what = ln.split(" ", 2)
                findings.append((lv, name, what))
                say(f"    [{lv}] {what}")
            elif ln.startswith("MODAL "):
                say(f"    (모달) {ln[6:]}")
            elif ln.strip():
                say(f"    {ln}")

    say("\n\n=== 찾은 것 ===")
    order = {"치명": 0, "높음": 1, "보통": 2, "낮음": 3}
    for lv, where, what in sorted(findings, key=lambda f: order.get(f[0], 9)):
        say(f"[{lv}] {where} — {what}")
    say(f"\n총 {len(findings)}건")
    io.open(LOG, "w", encoding="utf-8").write("\n".join(lines))
    print("done")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--one":
        _one(sys.argv[2])
    else:
        run_all()
