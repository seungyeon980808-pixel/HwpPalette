# -*- coding: utf-8 -*-
r"""도구줄 좌우 분할 미리보기 (2026-07-30).

앱 전체를 띄우지 않고 `dock_bar.DockBar` 만 실제 팔레트 데이터로 그려서
png 로 떠 놓는다 — 위계(공통/개인)가 눈에 보이는지, 빈 자리가 남는지
확인하려는 것이다. 아무것도 바꾸지 않는다 (칩을 눌러도 로그만 찍는다).

실행: python spikes/dock_bar_preview.py  →  spikes/_dock_bar_preview.png
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
import tkinter.font as tkfont

from hwp_palette.design import theme
from hwp_palette.model import palette
from hwp_palette.ui import dock_bar

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "_dock_bar_preview.png")
WIDTH = 1180


def main():
    root = tk.Tk()
    root.title("도구줄 미리보기")
    root.configure(bg=theme.colors()["bg"])
    root.geometry(f"{WIDTH}x220+60+60")

    def font_fn(size):
        return tkfont.Font(family="IBM Plex Sans KR", size=size)

    def label_fn(blk):
        return (blk.get("caption") or blk.get("name")
                or blk.get("value") or blk.get("key") or "?")

    tabs = palette.load_tabs()
    print("탭:", [t.get("name") for t in tabs])
    for t in tabs:
        print(f"  {t.get('name')}: 블럭 {len(t.get('blocks', []))}개")

    bar = dock_bar.DockBar(
        root, scale=1.0, font_fn=font_fn,
        run_block=lambda b: print("클릭:", label_fn(b)),
        label_fn=label_fn, block_color_fn=theme.block_color,
        tabs_fn=palette.load_tabs, tab_index_fn=lambda: 0,
        on_pick_tab=lambda i: None, on_undock=lambda: None,
        mode_label="임베드", on_toggle_mode=lambda: None)
    bar.pack(fill="x")
    tk.Frame(root, bg=theme.colors()["border"], height=1).pack(fill="x")
    tk.Label(root, text="↓ 이 아래가 한글 자리 ↓",
             bg=theme.colors()["subbg"], fg=theme.colors()["faint"],
             font=font_fn(9)).pack(fill="both", expand=True)

    def shoot():
        root.update_idletasks()
        root.update()
        try:
            from PIL import ImageGrab
            x, y = root.winfo_rootx(), root.winfo_rooty()
            w, h = root.winfo_width(), root.winfo_height()
            ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(OUT)
            print("저장:", OUT)
            print("도구줄 높이 =", bar.winfo_height(), "px")
        except Exception as e:
            print("스크린샷 실패:", e)
        root.destroy()

    root.after(1200, shoot)
    root.mainloop()


if __name__ == "__main__":
    main()
