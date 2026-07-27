# -*- coding: utf-8 -*-
"""양식 설정 창 (Toplevel).

- 위: 프리셋 선택 + 새로만들기/복제/이름변경/삭제/내보내기/가져오기
- 가운데: 그룹별 입력 폼 (스크롤). FIELD_SPEC 리스트로 자동 생성.
- 아래: 저장 / 닫기

저장하면 on_saved 콜백으로 활성 스펙을 호출부(main.py)에 알려 hwp_engine에 반영한다.
"""

import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
import dialogs as messagebox   # 윈도우 기본 대화상자 대신 프로그램과 같은 얼굴 (2026-07-27)

import settings

# ── 폼 필드 정의: (그룹, 경로, 라벨, 타입) ──────────────
# 타입: float / int / str / bool / font / border
FIELD_SPEC = [
    ("전체 폭",   ["layout", "column_width_mm"], "단 폭 (mm)  ·  2단≈93.99, 1단≈155", "float"),

    ("글꼴",     ["font", "apply"],   "글꼴 강제 적용 (끄면 문서 기본 글꼴 유지)", "bool"),
    ("글꼴",     ["font", "name"],    "글꼴", "font"),
    ("글꼴",     ["font", "size_pt"], "글자 크기 (pt)", "float"),

    ("자료박스", ["material_box", "row1_height_mm"], "내용 칸 최소 높이 (mm)", "float"),
    ("자료박스", ["material_box", "row2_height_mm"], "아래 여백 (mm)", "float"),

    ("사진박스", ["photo_box", "row1_height_mm"], "내용 칸 최소 높이 (mm)", "float"),
    ("사진박스", ["photo_box", "row2_height_mm"], "아래 여백 (mm)", "float"),

    ("실험박스", ["experiment_box", "height_mm"], "최소 높이 (mm)", "float"),
    ("실험박스", ["experiment_box", "label"],     "안내 문구", "str"),

    ("보기박스", ["bogi_box", "content_height_mm"],  "내용 칸 최소 높이 (mm)", "float"),
    ("보기박스", ["bogi_box", "title"],             "제목", "str"),
    ("보기박스", ["bogi_box", "line_spacing"],      "줄간격 (%)", "int"),
    ("보기박스", ["bogi_box", "cell_margin_left_mm"],   "셀 왼쪽 여백 (mm)", "float"),
    ("보기박스", ["bogi_box", "cell_margin_right_mm"],  "셀 오른쪽 여백 (mm)", "float"),
    ("보기박스", ["bogi_box", "cell_margin_top_mm"],    "셀 위 여백 (mm)", "float"),
    ("보기박스", ["bogi_box", "cell_margin_bottom_mm"], "셀 아래 여백 (mm)", "float"),
    ("보기박스", ["bogi_box", "title_height_mm"], "제목 위 칸 높이 (mm)", "float"),
    ("보기박스", ["bogi_box", "gap_height_mm"],   "제목 아래 칸 높이 (mm)", "float"),

    ("선지",     ["choices", "row_height_mm"], "행 최소 높이 (mm)", "float"),

    ("발문",     ["stem", "indentation"],  "내어쓰기 (음수, 한글 단위)", "int"),
    ("발문",     ["stem", "line_spacing"], "줄간격 (%)", "int"),

    ("질문",     ["question", "prev_spacing"], "위 간격", "int"),
    ("질문",     ["question", "next_spacing"], "아래 간격", "int"),

    ("테두리",   ["border", "material_type"],   "자료박스 테두리", "border"),
    ("테두리",   ["border", "bogi_type"],       "보기박스 테두리", "border"),
    ("테두리",   ["border", "experiment_type"], "실험박스 테두리", "border"),
]

FONT_CHOICES   = ["함초롬바탕", "함초롬돋움", "굴림", "바탕", "돋움", "맑은 고딕", "HY중고딕"]
BORDER_LABELS  = [("없음", "None"), ("실선", "Solid"), ("점선", "Dash"), ("이중선", "Double")]
BORDER_TO_LABEL = {v: k for k, v in BORDER_LABELS}
LABEL_TO_BORDER = {k: v for k, v in BORDER_LABELS}


def _get(spec, path):
    d = spec
    for p in path:
        d = d[p]
    return d


def _set(spec, path, value):
    d = spec
    for p in path[:-1]:
        d = d[p]
    d[path[-1]] = value


class SettingsWindow(tk.Toplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.on_saved = on_saved
        self.title("양식 설정")
        self.configure(bg="#f5f5f7")
        self.resizable(False, True)
        self.attributes("-topmost", True)

        self.current_name = settings.get_active_name()
        self.spec = settings.get_spec(self.current_name)
        self.vars = {}   # path tuple -> tk var

        self._build_profile_bar()
        self._build_form()
        self._build_footer()
        self._load_into_form()

        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx()-360}+{master.winfo_rooty()}")

    # ── 프리셋 바 ─────────────────────────────────────
    def _build_profile_bar(self):
        bar = tk.Frame(self, bg="#ffffff", padx=12, pady=10)
        bar.pack(fill="x")

        tk.Label(bar, text="양식 프리셋", font=("맑은 고딕", 9, "bold"),
                 bg="#ffffff", fg="#1d1d1f").pack(anchor="w")

        row = tk.Frame(bar, bg="#ffffff")
        row.pack(fill="x", pady=(6, 0))

        self.profile_var = tk.StringVar(value=self.current_name)
        self.profile_combo = ttk.Combobox(
            row, textvariable=self.profile_var, state="readonly",
            values=settings.list_profiles(), width=22)
        self.profile_combo.pack(side="left")
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_change)

        for text, cmd in [("＋ 새로", self._new_profile),
                          ("복제", self._duplicate_profile),
                          ("이름변경", self._rename_profile),
                          ("삭제", self._delete_profile)]:
            tk.Button(row, text=text, command=cmd, font=("맑은 고딕", 8),
                      bg="#e8e8ed", fg="#1d1d1f", bd=0, padx=8, pady=3,
                      cursor="hand2").pack(side="left", padx=(4, 0))

        row2 = tk.Frame(bar, bg="#ffffff")
        row2.pack(fill="x", pady=(6, 0))
        for text, cmd in [("📤 내보내기", self._export_profile),
                          ("📥 가져오기", self._import_profile)]:
            tk.Button(row2, text=text, command=cmd, font=("맑은 고딕", 8),
                      bg="#e8e8ed", fg="#1d1d1f", bd=0, padx=8, pady=3,
                      cursor="hand2").pack(side="left", padx=(0, 4))

    # ── 폼 (스크롤 영역) ──────────────────────────────
    def _build_form(self):
        wrap = tk.Frame(self, bg="#f5f5f7")
        wrap.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        canvas = tk.Canvas(wrap, bg="#f5f5f7", highlightthickness=0,
                           width=440, height=380)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        self.form = tk.Frame(canvas, bg="#f5f5f7")
        self.form.bind("<Configure>",
                       lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.form, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        self._canvas = canvas

        # 높이 동작 안내 (한글 표의 행 높이는 '최소값'으로만 동작)
        tk.Label(self.form,
                 text="※ 높이는 '최소 높이'입니다. 내용 줄 수·줄간격·셀 여백이\n"
                      "   만드는 높이보다 작게는 줄어들지 않습니다.",
                 font=("맑은 고딕", 8), bg="#f5f5f7", fg="#86868b",
                 justify="left").pack(anchor="w", pady=(0, 6))

        # 그룹별로 LabelFrame 만들고 필드 배치
        groups = {}
        for group, path, label, ftype in FIELD_SPEC:
            if group not in groups:
                lf = tk.LabelFrame(self.form, text=group, font=("맑은 고딕", 9, "bold"),
                                   bg="#ffffff", fg="#0071e3", bd=1,
                                   relief="solid", padx=10, pady=8)
                lf.pack(fill="x", pady=(0, 8))
                lf.grid_columnconfigure(1, weight=1)
                groups[group] = [lf, 0]
                # 보기박스 그룹 상단에 '시각 편집' 진입 버튼
                if group == "보기박스":
                    tk.Button(lf, text="도식 보며 편집",
                              command=self._open_bogi_visual,
                              font=("맑은 고딕", 9, "bold"), bg="#0071e3", fg="white",
                              bd=0, padx=10, pady=4, cursor="hand2").grid(
                              row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
                    groups[group][1] = 1
            lf, r = groups[group]
            self._add_field(lf, r, path, label, ftype)
            groups[group][1] = r + 1

    def _open_bogi_visual(self):
        import bogi_visual_ui  # 순환 참조 회피 (bogi_visual_ui → settings_ui)

        def after_saved():
            # 시각 편집에서 저장 → 폼도 새 값으로 갱신 + 상위 콜백 전달
            self.spec = settings.get_spec(self.current_name)
            self._load_into_form()
            self._notify_saved()

        bogi_visual_ui.open_editor(self, on_saved=after_saved)

    def _add_field(self, parent, row, path, label, ftype):
        key = tuple(path)
        tk.Label(parent, text=label, font=("맑은 고딕", 9),
                 bg="#ffffff", fg="#1d1d1f", anchor="w").grid(
                 row=row, column=0, sticky="w", pady=3, padx=(0, 8))

        if ftype == "bool":
            var = tk.BooleanVar()
            tk.Checkbutton(parent, variable=var, bg="#ffffff",
                           activebackground="#ffffff").grid(
                           row=row, column=1, sticky="w")
        elif ftype == "font":
            var = tk.StringVar()
            ttk.Combobox(parent, textvariable=var, values=FONT_CHOICES,
                         width=16).grid(row=row, column=1, sticky="e")
        elif ftype == "border":
            var = tk.StringVar()
            ttk.Combobox(parent, textvariable=var,
                         values=[k for k, _ in BORDER_LABELS], state="readonly",
                         width=16).grid(row=row, column=1, sticky="e")
        else:  # float / int / str
            var = tk.StringVar()
            tk.Entry(parent, textvariable=var, width=18, justify="right",
                     relief="solid", bd=1).grid(row=row, column=1, sticky="e")

        self.vars[key] = (var, ftype)

    # ── 폼 ↔ spec ─────────────────────────────────────
    def _load_into_form(self):
        for key, (var, ftype) in self.vars.items():
            val = _get(self.spec, list(key))
            if ftype == "border":
                var.set(BORDER_TO_LABEL.get(val, "실선"))
            else:
                var.set(val)

    def _collect_from_form(self):
        """폼 값을 self.spec에 반영. 숫자 파싱 실패 시 예외."""
        for key, (var, ftype) in self.vars.items():
            raw = var.get()
            if ftype == "float":
                value = float(raw)
            elif ftype == "int":
                value = int(float(raw))
            elif ftype == "bool":
                value = bool(var.get())
            elif ftype == "border":
                value = LABEL_TO_BORDER.get(raw, "Solid")
            else:  # str / font
                value = str(raw)
            _set(self.spec, list(key), value)

    # ── 프리셋 조작 ───────────────────────────────────
    def _refresh_combo(self, select=None):
        names = settings.list_profiles()
        self.profile_combo["values"] = names
        if select:
            self.profile_var.set(select)
            self.current_name = select

    def _on_profile_change(self, event=None):
        name = self.profile_var.get()
        if name == self.current_name:
            return
        if not self._confirm_discard():
            self.profile_var.set(self.current_name)
            return
        settings.set_active_name(name)
        self.current_name = name
        self.spec = settings.get_spec(name)
        self._load_into_form()
        self._notify_saved()

    def _confirm_discard(self):
        return messagebox.askyesno(
            "확인", "저장하지 않은 변경 내용은 사라집니다. 계속할까요?",
            parent=self)

    def _new_profile(self):
        name = simpledialog.askstring("새 프리셋", "새 양식 이름:", parent=self)
        if not name:
            return
        try:
            settings.add_profile(name)
            self.current_name = name
            self.spec = settings.get_spec(name)
            self._refresh_combo(select=name)
            self._load_into_form()
            self._notify_saved()
        except Exception as e:
            messagebox.showerror("오류", str(e), parent=self)

    def _duplicate_profile(self):
        name = simpledialog.askstring(
            "프리셋 복제", f"'{self.current_name}' 복제본 이름:", parent=self)
        if not name:
            return
        try:
            settings.duplicate_profile(self.current_name, name)
            self.current_name = name
            self.spec = settings.get_spec(name)
            self._refresh_combo(select=name)
            self._load_into_form()
            self._notify_saved()
        except Exception as e:
            messagebox.showerror("오류", str(e), parent=self)

    def _rename_profile(self):
        name = simpledialog.askstring(
            "이름 변경", "새 이름:", initialvalue=self.current_name, parent=self)
        if not name or name == self.current_name:
            return
        try:
            settings.rename_profile(self.current_name, name)
            self.current_name = name
            self._refresh_combo(select=name)
            self._notify_saved()
        except Exception as e:
            messagebox.showerror("오류", str(e), parent=self)

    def _delete_profile(self):
        if not messagebox.askyesno(
                "삭제", f"'{self.current_name}' 프리셋을 삭제할까요?", parent=self):
            return
        try:
            settings.delete_profile(self.current_name)
            new_active = settings.get_active_name()
            self.current_name = new_active
            self.spec = settings.get_spec(new_active)
            self._refresh_combo(select=new_active)
            self._load_into_form()
            self._notify_saved()
        except Exception as e:
            messagebox.showerror("오류", str(e), parent=self)

    def _export_profile(self):
        path = filedialog.asksaveasfilename(
            title="프리셋 내보내기", defaultextension=".json",
            initialfile=f"{self.current_name}.json",
            filetypes=[("JSON", "*.json")], parent=self)
        if not path:
            return
        try:
            settings.export_profile(self.current_name, path)
            messagebox.showinfo("완료", "프리셋을 내보냈습니다.", parent=self)
        except Exception as e:
            messagebox.showerror("오류", str(e), parent=self)

    def _import_profile(self):
        path = filedialog.askopenfilename(
            title="프리셋 가져오기", filetypes=[("JSON", "*.json")], parent=self)
        if not path:
            return
        try:
            name = settings.import_profile(path)
            self.current_name = name
            self.spec = settings.get_spec(name)
            self._refresh_combo(select=name)
            self._load_into_form()
            self._notify_saved()
            messagebox.showinfo("완료", f"'{name}' 프리셋을 가져왔습니다.", parent=self)
        except Exception as e:
            messagebox.showerror("오류", str(e), parent=self)

    # ── 저장/닫기 ─────────────────────────────────────
    def _build_footer(self):
        foot = tk.Frame(self, bg="#f5f5f7", padx=12, pady=10)
        foot.pack(fill="x")
        tk.Button(foot, text="💾 저장", command=self._save,
                  font=("맑은 고딕", 10, "bold"), bg="#0071e3", fg="white",
                  bd=0, padx=16, pady=7, cursor="hand2").pack(side="left")
        tk.Button(foot, text="닫기", command=self.destroy,
                  font=("맑은 고딕", 10), bg="#e8e8ed", fg="#1d1d1f",
                  bd=0, padx=16, pady=7, cursor="hand2").pack(side="right")

    def _save(self):
        try:
            self._collect_from_form()
        except ValueError:
            messagebox.showerror(
                "입력 오류", "숫자 칸에 올바른 값을 입력해주세요.", parent=self)
            return
        settings.save_profile(self.current_name, self.spec)
        settings.set_active_name(self.current_name)
        self._notify_saved()
        messagebox.showinfo("저장", "양식을 저장했습니다.", parent=self)

    def _notify_saved(self):
        """활성 스펙을 호출부에 알린다 (hwp_engine 반영용)."""
        if self.on_saved:
            self.on_saved(settings.get_active_spec())


def open_settings(master, on_saved=None):
    return SettingsWindow(master, on_saved=on_saved)
