# -*- coding: utf-8 -*-
r"""자간 자동 보정(피드백 016) 실측 스파이크 — 방식 A 가 가능한지 재 본다.

왜 만드나: 016 의 1차 기술 검토는 "가능해 보인다 — 실측 필요"에서 멈춰 있다.
방식 A(어절 단위 줄바꿈을 켠 채, 헐렁한 줄만 자간을 좁혀 다음 줄 첫 어절을
당겨 올림)를 구현하려면 **네 가지**가 실제로 되는지부터 알아야 한다.

    ① 시각적 '한 줄'을 선택하거나 줄 끝 위치를 알아낼 수 있는가
    ② 그 줄의 '남는 폭'을 잴 수 있는가 — 못 재면 "해 보고 되돌리기"가 실용적인가
    ③ 자간(CharShape.Spacing)을 선택 영역에만 걸고 되돌릴 수 있는가
    ④ 한 문단의 자간을 바꾸면 아래 문단까지 다시 흐르는가

이 스파이크는 그 넷을 **직접 재기 위한 일회용 실험 도구**다. 앱 코드는 건드리지
않는다 — spikes/ 는 제품에 포함되지 않는다.

안전: 실행 중인 한글에는 절대 손대지 않는다. DispatchEx 로 **전용 인스턴스**를
새로 띄우고 그 안에서만 새 문서를 만든다. 끝나면 저장하지 않고 버린다.
(embed_spike.py 와 같은 관례 — 선생님이 열어 둔 문서는 위험하지 않다.)

실행:
    python spikes\spacing_fit_spike.py            # 창을 띄우고 실측
    python spikes\spacing_fit_spike.py --keep     # 끝나도 한글을 안 닫는다(눈으로 확인용)
    python spikes\spacing_fit_spike.py --hidden   # 창을 숨긴 채 (빠르지만 눈으로 못 봄)

결과는 화면과 spikes\spacing_fit_spike.log 에 같이 남는다.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32com.client

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "spacing_fit_spike.log")

# 실측용 본문 — 어절 길이가 들쭉날쭉해야 '헐렁한 줄'이 생긴다.
# 짧은 어절만 있으면 줄 끝이 늘 꽉 차서 잴 것이 없다.
PARAS = [
    "우리 학교 과학실에서는 매주 화요일마다 학생들이 직접 실험 기구를 준비하고 "
    "관찰 결과를 기록하는 활동을 진행하는데, 이때 안전 수칙을 반드시 지켜야 한다.",
    "광합성이라는 현상은 식물이 빛에너지를 이용하여 이산화탄소와 물로부터 포도당을 "
    "만들어내는 과정이며, 이 과정에서 부산물로 산소가 발생한다는 사실은 널리 알려져 있다.",
    "전자기유도현상은 코일을 통과하는 자기력선의 개수가 변할 때 코일에 유도전류가 "
    "흐르는 현상으로, 발전기와 변압기의 작동 원리를 설명하는 데에 핵심적으로 사용된다.",
    "짧은 문단.",
    # 마지막 문단은 일부러 길게 — 방식 A 예행(M5)에서 여러 줄을 훑어야 한다
    "지구온난화로 인하여 극지방의 빙하가 녹아내리고 해수면이 상승하면서 저지대 도시가 "
    "침수될 위험이 커지고 있으므로 온실기체 배출량을 줄이려는 국제적인 노력이 필요하다. "
    "특히 이산화탄소와 메테인처럼 대기 중에 오래 머무르는 기체는 지표면에서 방출되는 "
    "적외선을 흡수하였다가 다시 내보내는 성질을 가지고 있어서 대기의 평균 온도를 "
    "끌어올리는 데에 결정적인 역할을 하며, 이러한 온실효과가 지나치게 강해지면 "
    "생태계 전반에 걸쳐 되돌리기 어려운 변화가 나타나게 된다.",
]

_log_f = None


def log(msg=""):
    global _log_f
    if _log_f is None:
        _log_f = open(LOG_PATH, "a", encoding="utf-8")
        _log_f.write(f"\n{'=' * 70}\n{time.strftime('%Y-%m-%d %H:%M:%S')} 새 실행\n")
    print(msg)
    _log_f.write(str(msg) + "\n")
    _log_f.flush()


# ── 얇은 도우미들 ────────────────────────────────────────
def run(hwp, action):
    """액션 하나 실행. 없는 이름이면 예외/False 가 오므로 그대로 돌려준다."""
    try:
        return hwp.HAction.Run(action)
    except Exception as e:
        return f"예외: {e}"


def pos(hwp):
    """(list, para, pos). 우리 앱 current_pos() 와 같은 값."""
    return tuple(hwp.GetPos())


def sel_text(hwp):
    """선택 영역 글자 — 클립보드를 안 거치는 방식(앱의 read_selection_direct 관례)."""
    try:
        return hwp.GetTextFile("TEXT", "saveblock") or ""
    except Exception as e:
        return f"<읽기 실패: {e}>"


def key_indicator(hwp):
    """상태 표시줄 값 묶음. 인덱스 의미는 아래 M0 에서 실측으로 알아낸다."""
    try:
        return tuple(hwp.KeyIndicator())
    except Exception as e:
        return f"<KeyIndicator 실패: {e}>"


# 실측(M0)으로 확정한 KeyIndicator 자리 — 5=줄번호, 6=칸번호(반각 1칸 단위, 1부터)
KI_LINE, KI_COL = 5, 6


def col(hwp):
    """지금 커서의 '칸 번호'. 한글 한 글자 = 2칸이라 폭의 대용치로 쓸 수 있다."""
    ki = key_indicator(hwp)
    return ki[KI_COL] if isinstance(ki, tuple) else -1


def dump_props(obj, title):
    """타입 라이브러리가 아는 속성 이름을 통째로 뽑는다 — 이름을 추측하지 않기 위해."""
    try:
        names = sorted(set(list(getattr(obj, "_prop_map_get_", {}).keys())
                           + list(getattr(obj, "_prop_map_put_", {}).keys())))
    except Exception as e:
        log(f"[{title}] 속성 목록 실패: {e}")
        return []
    log(f"\n[{title}] 속성 {len(names)}개")
    for i in range(0, len(names), 6):
        log("  " + ", ".join(names[i:i + 6]))
    return names


def set_para_field(hwp, para, field, value):
    """한 문단의 문단모양 필드 하나를 바꾸고 **되읽어서** 실제로 먹었는지 확인한다.

    왜 되읽나: Execute 가 True 를 줘도 값이 안 바뀌는 경우가 있다. 지정값만 믿고
    "어절 단위를 켰다"고 적으면 실측이 아니라 추측이 된다.
    """
    ps = hwp.HParameterSet
    try:
        hwp.SetPos(0, para, 0)
        run(hwp, "MoveParaBegin")
        run(hwp, "MoveSelParaEnd")
        hwp.HAction.GetDefault("ParagraphShape", ps.HParaShape.HSet)
        setattr(ps.HParaShape, field, value)
        hwp.HAction.Execute("ParagraphShape", ps.HParaShape.HSet)
        run(hwp, "Cancel")
        hwp.SetPos(0, para, 0)
        hwp.HAction.GetDefault("ParagraphShape", ps.HParaShape.HSet)
        return getattr(ps.HParaShape, field)
    except Exception as e:
        return f"<실패: {e}>"


def probe(obj, names, title):
    """이름 목록을 하나씩 만져 보고 있는 것만 남긴다 — 추측 대신 실측."""
    log(f"\n[{title}]")
    have, miss = [], []
    for n in names:
        try:
            getattr(obj, n)
            have.append(n)
        except Exception:
            miss.append(n)
    log(f"  있음: {', '.join(have) if have else '(없음)'}")
    log(f"  없음: {', '.join(miss) if miss else '(없음)'}")
    return have


# ── 준비 ─────────────────────────────────────────────────
def spawn(hidden=False):
    hwp = win32com.client.DispatchEx("HWPFrame.HwpObject")
    try:
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception as e:
        log(f"보안모듈 등록 실패(무시): {e}")
    try:
        # 저장 여부 같은 모달 대화상자가 뜨면 스파이크가 그대로 멈춘다.
        hwp.SetMessageBoxMode(0x00000020)   # 예/아니오 → '아니오' 자동 응답
    except Exception as e:
        log(f"SetMessageBoxMode 실패(무시): {e}")
    if not hidden:
        hwp.XHwpWindows.Item(0).Visible = True
    time.sleep(1.0)
    return hwp


def fill_doc(hwp):
    """긴 한국어 문단 여러 개를 넣는다. 문단 사이는 BreakPara 로 나눈다."""
    run(hwp, "FileNew")
    act, ps = hwp.HAction, hwp.HParameterSet
    for i, p in enumerate(PARAS):
        act.GetDefault("InsertText", ps.HInsertText.HSet)
        ps.HInsertText.Text = p
        act.Execute("InsertText", ps.HInsertText.HSet)
        if i != len(PARAS) - 1:
            run(hwp, "BreakPara")
    run(hwp, "MoveDocBegin")


# ── M0. 상태값·API 재고 조사 ─────────────────────────────
def m0_inventory(hwp):
    log("\n" + "─" * 70)
    log("M0. 무엇이 있는지부터 — 있는 API 만 가지고 설계해야 한다")
    log("─" * 70)

    probe(hwp, [
        "GetPos", "SetPos", "GetPosBySet", "SetPosBySet",
        "KeyIndicator", "GetTextFile", "GetPageText", "PageCount",
        "SelectionMode", "PointToHwpUnit", "HwpUnitToPoint",
        "GetSelectedPos", "GetSelectedPosBySet",
        # 아래는 '커서의 화면 좌표'를 줄 만한 이름들 — 있으면 남는 폭을 바로 잴 수 있다
        "GetCaretPos", "CaretPos", "GetCursorPos", "PositionToRect",
        "GetPosRect", "XHwpDocuments", "ViewProperties", "HeadCtrl",
    ], "hwp 최상위 멤버")

    # 자간을 어디에 넣어야 하는지 — CharShape 에 Spacing 이라는 단일 필드는 없고
    # 글자 종류(한글/영문/한자/…)마다 따로다. 이름을 추측하지 말고 통째로 뽑는다.
    ps = hwp.HParameterSet
    try:
        hwp.HAction.GetDefault("CharShape", ps.HCharShape.HSet)
    except Exception as e:
        log(f"  CharShape GetDefault 실패: {e}")
    names = dump_props(ps.HCharShape, "HCharShape")
    for n in [x for x in names if x.startswith(("Spacing", "Ratio"))]:
        try:
            log(f"    현재값 {n} = {getattr(ps.HCharShape, n)}")
        except Exception:
            pass

    # 어절 단위 줄바꿈이 문단 모양 어디에 있는지
    try:
        hwp.HAction.GetDefault("ParagraphShape", ps.HParaShape.HSet)
    except Exception as e:
        log(f"  ParagraphShape GetDefault 실패: {e}")
    pshp = probe(ps.HParaShape, [
        "BreakLatinWord", "BreakNonLatinWord", "SnapToGrid", "AlignType",
        "Condense", "LineSpacing", "LineSpacingType",
    ], "HParaShape 필드 (어절 단위 줄바꿈·자간 자동좁힘 후보)")
    for n in pshp:
        try:
            log(f"    현재값 {n} = {getattr(ps.HParaShape, n)}")
        except Exception:
            pass

    # 본문 폭(= 한 줄에 쓸 수 있는 폭)을 알 수 있는가 — 용지 설정에서 계산.
    # HwpUnitToPoint 는 이 버전에 없어서 1pt = 100 HWPUNIT 로 직접 나눈다.
    try:
        hwp.HAction.GetDefault("PageSetup", ps.HSecDef.HSet)
        pg = ps.HSecDef.PageDef
        w, lm, rm = pg.PaperWidth, pg.LeftMargin, pg.RightMargin
        body = w - lm - rm
        log(f"\n[용지] 폭={w} 왼여백={lm} 오른여백={rm} "
            f"→ 본문폭={body} HWPUNIT ({body / 100:.1f}pt)")
        h = ps.HCharShape.Height          # 글자 크기(HWPUNIT)
        log(f"  글자크기={h} HWPUNIT ({h / 100:.1f}pt) "
            f"→ 이론상 한 줄 한글 {body / h:.1f}자 = {2 * body / h:.1f}칸")
    except Exception as e:
        log(f"\n[용지] 읽기 실패: {e}")

    # GetPosBySet 이 좌표까지 주는지 — 준다면 남는 폭을 바로 잴 수 있다
    try:
        pset = hwp.GetPosBySet()
        dump_props(pset, "GetPosBySet 결과")
        for k in ("List", "Para", "Pos"):
            try:
                log(f"    Item({k!r}) = {pset.Item(k)}")
            except Exception as e:
                log(f"    Item({k!r}) 실패: {e}")
    except Exception as e:
        log(f"\n[GetPosBySet] 실패: {e}")

    # KeyIndicator 의 어느 칸이 '줄 번호'인지 — 한 줄 내려 보고 바뀌는 칸을 찾는다
    run(hwp, "MoveDocBegin")
    a = key_indicator(hwp)
    run(hwp, "MoveLineDown")
    b = key_indicator(hwp)
    run(hwp, "MoveDocBegin")
    log(f"\n[KeyIndicator] 문서맨앞={a}")
    log(f"[KeyIndicator] 한 줄 아래={b}")
    if isinstance(a, tuple) and isinstance(b, tuple) and len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        log(f"  → 한 줄 내렸을 때 달라진 칸 index = {diff}")


# ── M1. 시각적 한 줄을 잡을 수 있는가 ────────────────────
def m1_line_select(hwp):
    log("\n" + "─" * 70)
    log("M1. 시각적 '한 줄'을 선택/판정할 수 있는가")
    log("─" * 70)

    for act in ("MoveLineBegin", "MoveLineEnd", "MoveLineUp", "MoveLineDown",
                "MoveSelLineBegin", "MoveSelLineEnd",
                "MoveParaBegin", "MoveParaEnd", "MoveSelParaEnd",
                "MoveNextWord", "MovePrevWord", "MoveSelNextWord",
                "MoveSelPrevWord", "MoveRight", "MoveLeft"):
        run(hwp, "MoveDocBegin")
        r = run(hwp, act)
        run(hwp, "Cancel")
        log(f"  {act:18s} → {r}")

    log("\n첫 문단을 줄 단위로 훑는다 (MoveLineBegin → MoveSelLineEnd):")
    run(hwp, "MoveDocBegin")
    log(f"  MoveDocBegin 직후 GetPos = {pos(hwp)}  ← pos 의 기준점 확인")
    lines = scan_lines(hwp, para=0)
    for i, (b, e, t, c) in enumerate(lines):
        log(f"  줄{i}: pos {b[2]}~{e[2]} ({e[2] - b[2]}자) 끝칸={c} | {t}")
    log(f"  → 첫 문단은 시각적으로 {len(lines)}줄. "
        f"문단 전체가 한 덩어리로 잡히지 않고 줄마다 끊기면 ① 성공.")

    # 어절 단위 줄바꿈은 **여러 줄로 흐르는 긴 문단**에서만 차이가 드러난다.
    # (2줄짜리 문단으로 재면 우연히 같은 자리에서 끊겨 '차이 없음'으로 보인다 —
    #  첫 실행에서 실제로 그렇게 잘못 읽을 뻔했다.)
    log("\n어절 단위 줄바꿈(BreakNonLatinWord)에 따라 줄 끝이 어떻게 달라지나 "
        "— 긴 문단4 로 잰다:")
    for v in (0, 1):
        got = set_para_field(hwp, 4, "BreakNonLatinWord", v)
        ls = scan_lines(hwp, 4)
        log(f"  BreakNonLatinWord 지정={v} 되읽음={got}: 줄수={len(ls)}")
        for i, (b, e, t, c) in enumerate(ls):
            cut = "" if (t.endswith(" ") or i == len(ls) - 1) else "  ← 단어 중간에서 잘림"
            log(f"    줄{i} 끝칸={c} 끝부분='…{t[-10:]}'{cut}")
        log(f"    왼쪽 정렬로 잰 줄별 남는 칸 = {slack_by_left_align(hwp, 4)}")
    set_para_field(hwp, 4, "BreakNonLatinWord", 1)      # 원래대로(한글 기본값)
    return scan_lines(hwp, 0)


def scan_lines(hwp, para, max_lines=40, with_text=True):
    """한 문단을 시각적 줄 단위로 훑어 [(줄시작pos, 줄끝pos, 글자, 끝칸)] 를 준다.

    왜 이렇게: 문단 안 어디서든 MoveLineBegin/MoveSelLineEnd 를 걸면 '지금 커서가
    놓인 시각적 줄'이 잡힌다. 줄 끝에서 MoveRight 를 한 번 더 하면 다음 줄
    첫 글자로 넘어가므로, 그걸 반복하면 문단이 몇 줄로 흐르는지 알 수 있다.

    '끝칸' = 줄 끝에서의 KeyIndicator 칸 번호. 한글 한 글자가 2칸이라 이 값이
    **그 줄이 실제로 쓴 폭**의 대용치가 된다 — 남는 폭 판정의 핵심 재료.
    """
    out = []
    hwp.SetPos(0, para, 0)
    for _ in range(max_lines):
        run(hwp, "MoveLineBegin")
        b = pos(hwp)
        if b[1] != para:
            break
        t = ""
        if with_text:
            run(hwp, "MoveSelLineEnd")
            t = sel_text(hwp)
            run(hwp, "Cancel")
        run(hwp, "MoveLineEnd")
        e = pos(hwp)
        out.append((b, e, t, col(hwp)))
        run(hwp, "MoveRight")           # 다음 줄 첫 글자로
        if pos(hwp)[1] != para:
            break
        if pos(hwp)[2] <= e[2]:         # 더 못 나아가면 마지막 줄
            break
    return out


# ── M2. 줄의 '남는 폭'을 알 수 있는가 ────────────────────
def m2_slack(hwp, lines):
    log("\n" + "─" * 70)
    log("M2. 줄의 남는 폭 — 직접 잴 수 있는가, 아니면 '해 보고 되돌리기'인가")
    log("─" * 70)

    log("\n(가) 직접 재기: 줄 끝에서 커서의 가로 좌표를 주는 API 가 있는가")
    hwp.SetPos(0, 0, 0)
    run(hwp, "MoveLineEnd")
    for name in ("GetPosBySet", "GetSelectedPosBySet", "KeyIndicator"):
        try:
            v = getattr(hwp, name)()
            log(f"  {name}() = {v}")
        except Exception as e:
            log(f"  {name}() 실패: {e}")

    log("\n(나) 칸 번호로 간접 재기 — 줄이 실제로 쓴 폭")
    log("  각 문단의 줄별 (글자수, 끝칸):")
    maxcol = 0
    for p in range(len(PARAS)):
        ls = scan_lines(hwp, p, with_text=False)
        log(f"   문단{p}: {[(e[2] - b[2], c) for b, e, _, c in ls]}")
        # 마지막 줄은 문단이 끝나서 짧은 것이므로 '꽉 찬 줄' 후보에서 뺀다
        for *_, c in ls[:-1]:
            maxcol = max(maxcol, c)
    log(f"  → 관측된 최대 끝칸 = {maxcol} (이 줄이 '거의 꽉 찬' 줄)")
    for p in range(len(PARAS)):
        ls = scan_lines(hwp, p, with_text=False)
        log(f"   문단{p} 줄별 남는 칸 = {[maxcol - c for *_, c in ls[:-1]]}")
    log("  → 한글은 한 글자=2칸이므로 '남는 칸 ≥ 2' 면 최소 한 글자는 더 들어갈 폭.")

    log("\n(라) 양쪽 정렬이 남는 폭을 감추고 있는가 — 정렬을 바꿔 가며 끝칸을 본다")
    log("  (양쪽 정렬이면 한글이 어절 간격을 늘려 줄 끝을 여백에 딱 맞춘다.")
    log("   그러면 '끝칸'은 늘 꽉 찬 값이라 남는 폭을 못 잰다. 왼쪽 정렬로 바꾸면")
    log("   늘리기가 사라져 진짜 남는 폭이 드러난다 — 그게 사실인지 확인한다.)")
    for a in (0, 1, 2, 3):
        got = set_para_field(hwp, 4, "AlignType", a)
        ls = scan_lines(hwp, 4, with_text=False)
        log(f"  AlignType 지정={a} 되읽음={got}: 끝칸={[c for *_, c in ls]}")
    set_para_field(hwp, 4, "AlignType", 0)              # 원래대로(양쪽 정렬)

    log("\n(다) 되돌리기 방식이 실용적인가 — 자간을 좁혀 보고 줄이 바뀌는지 본다")
    t0 = time.time()
    before = [(b[2], e[2], c) for b, e, _, c in lines]
    apply_spacing(hwp, 0, lines[0][0][2], lines[0][1][2], -5)
    after_lines = scan_lines(hwp, 0, with_text=False)
    after = [(b[2], e[2], c) for b, e, _, c in after_lines]
    dt = time.time() - t0
    log(f"  자간 −5% 적용 전 줄 (시작,끝,끝칸) = {before}")
    log(f"  자간 −5% 적용 후 줄 (시작,끝,끝칸) = {after}")
    log(f"  줄 수 {len(before)} → {len(after)},  한 줄 시도에 걸린 시간 {dt:.2f}s")
    pulled = bool(after and before and after[0][1] > before[0][1])
    log(f"  → 첫 줄이 더 많은 글자를 담았는가: {pulled}")

    # 되돌리기
    apply_spacing(hwp, 0, after_lines[0][0][2], after_lines[0][1][2], 0)
    back = [(b[2], e[2], c) for b, e, _, c in scan_lines(hwp, 0, with_text=False)]
    log(f"  자간 0 으로 되돌린 뒤 = {back}")
    log(f"  → 원래대로 복구되는가: {back == before}")
    return dt


# 자간은 글자 종류마다 따로 있다 — 한글만 건드리면 섞인 영문·숫자가 안 따라온다.
SPACING_FIELDS = ("SpacingHangul", "SpacingLatin", "SpacingHanja",
                  "SpacingJapanese", "SpacingOther", "SpacingSymbol",
                  "SpacingUser")


def select_range(hwp, para, start, end):
    """[start, end) 를 선택한다. SelectText 가 있으면 그걸로 (한 번에 끝난다)."""
    try:
        hwp.SetPos(0, para, start)
        hwp.SelectText(para, start, para, end)
        if hwp.SelectionMode != 0:
            return "SelectText"
    except Exception:
        pass
    hwp.SetPos(0, para, start)          # 대안: 오른쪽으로 한 칸씩 선택 확장
    for _ in range(end - start):
        run(hwp, "MoveSelRight")
    return "MoveSelRight"


def apply_spacing(hwp, para, start, end, spacing_pct):
    """[start, end) 구간만 선택해 자간을 건다. 나머지 서식은 건드리지 않는다.

    왜 GetDefault 를 먼저 부르나: HSet 을 비운 채 Execute 하면 글꼴·크기까지
    기본값으로 덮어써 문서를 망친다. GetDefault 로 현재 서식을 불러온 뒤
    자간만 바꿔 넣는 것이 앱의 set_char_shape 관례와 같다.
    """
    select_range(hwp, para, start, end)
    act, ps = hwp.HAction, hwp.HParameterSet
    act.GetDefault("CharShape", ps.HCharShape.HSet)
    for f in SPACING_FIELDS:
        try:
            setattr(ps.HCharShape, f, spacing_pct)
        except Exception:
            pass
    act.Execute("CharShape", ps.HCharShape.HSet)
    run(hwp, "Cancel")


def read_spacing(hwp, para, p):
    """그 자리의 한글 자간 값."""
    hwp.SetPos(0, para, p)
    ps = hwp.HParameterSet
    hwp.HAction.GetDefault("CharShape", ps.HCharShape.HSet)
    return ps.HCharShape.SpacingHangul


# ── M3. 자간을 선택 영역에만 걸고 되돌릴 수 있는가 ───────
def m3_spacing_scope(hwp):
    log("\n" + "─" * 70)
    log("M3. 자간을 선택 영역에만 걸고 되돌릴 수 있는가")
    log("─" * 70)

    lines = scan_lines(hwp, 2, with_text=False)
    if len(lines) < 2:
        log("  2번 문단이 한 줄뿐 — 건너뜀")
        return
    b, e = lines[0][0], lines[0][1]
    mid = (b[2] + e[2]) // 2
    log(f"  선택 구간 = 문단2 pos {b[2]}~{e[2]}  (선택 수단: "
        f"{select_range(hwp, 2, b[2], e[2])})")
    run(hwp, "Cancel")
    apply_spacing(hwp, 2, b[2], e[2], -6)

    log(f"  건 자리(첫 줄 가운데 pos {mid}) 자간 = {read_spacing(hwp, 2, mid)}")
    log(f"  안 건 자리(둘째 줄 pos {e[2] + 3}) 자간 = "
        f"{read_spacing(hwp, 2, e[2] + 3)}")
    log(f"  줄 수 {len(lines)} → {len(scan_lines(hwp, 2, with_text=False))} "
        f"(자간 −6% 적용 뒤)")

    # 되돌리기 두 가지 — ⓐ 자간 0 재적용 ⓑ Undo
    now = scan_lines(hwp, 2, with_text=False)
    apply_spacing(hwp, 2, now[0][0][2], now[0][1][2], 0)
    log(f"  ⓐ 자간 0 재적용 뒤 = {read_spacing(hwp, 2, mid)}")

    apply_spacing(hwp, 2, b[2], e[2], -6)
    run(hwp, "Undo")
    log(f"  ⓑ Undo 한 번 뒤 = {read_spacing(hwp, 2, mid)} "
        f"(자간 적용이 되돌리기 한 칸으로 잡히는지)")
    run(hwp, "Undo")   # 혹시 남았으면 한 번 더


# ── M4. 재흐름 범위 ──────────────────────────────────────
def m4_reflow(hwp):
    log("\n" + "─" * 70)
    log("M4. 한 문단 자간을 바꾸면 아래 문단까지 다시 흐르는가")
    log("─" * 70)

    def snapshot():
        """문단마다 (문서상 줄번호, 줄수, 줄 경계) — 경계까지 봐야 재흐름이 보인다."""
        out = []
        for i in range(len(PARAS)):
            ls = scan_lines(hwp, i, with_text=False)
            hwp.SetPos(0, i, 0)
            ki = key_indicator(hwp)
            out.append((i,
                        ki[KI_LINE] if isinstance(ki, tuple) else -1,
                        len(ls),
                        [b[2] for b, *_ in ls]))
        return out

    before = snapshot()
    for i, ki, n, bs in before:
        log(f"  전 문단{i}: 문서줄번호={ki} 줄수={n} 줄시작={bs}")

    # 문단1 **전체**에 −8% — 한 줄만 건드리면 그 문단 안에서도 티가 잘 안 난다
    p1 = scan_lines(hwp, 1, with_text=False)
    apply_spacing(hwp, 1, p1[0][0][2], p1[-1][1][2], -8)
    after = snapshot()
    log("")
    for i, ki, n, bs in after:
        log(f"  후 문단{i}: 문서줄번호={ki} 줄수={n} 줄시작={bs}")

    log("\n  판정:")
    for (i, k1, n1, b1), (_, k2, n2, b2) in zip(before, after):
        tag = []
        if b1 != b2:
            tag.append("문단 안에서 줄이 다시 흐름")
        if n1 != n2:
            tag.append("줄수 변함")
        if k1 != k2:
            tag.append("문서상 줄 위치가 밀림")
        log(f"   문단{i}: {' / '.join(tag) if tag else '변화 없음'}")
    log("  → 손댄 문단만 '다시 흐름'이고 뒤 문단은 '줄 위치가 밀림'뿐이면, "
        "재흐름은 문단 경계를 넘지 않는다 = 위→아래 한 번 훑기로 충분하다.")

    apply_spacing(hwp, 1, p1[0][0][2], p1[-1][1][2], 0)


# ── M5. 방식 A 를 흉내 내 본다 ───────────────────────────
def slack_by_left_align(hwp, para, ref_col=None):
    """양쪽 정렬을 잠깐 왼쪽 정렬로 바꿔 '진짜 남는 칸'을 재고 되돌린다.

    왜 이렇게까지: 양쪽 정렬에서는 한글이 어절 간격을 늘려 줄 끝을 여백에 딱
    맞추므로 끝칸이 늘 꽉 찬 값이다. 그 상태로는 어느 줄이 헐렁한지 알 수 없다.
    정렬을 잠깐 풀면 늘리기가 사라져 남는 폭이 숫자로 드러난다.
    """
    orig = None
    try:
        ps = hwp.HParameterSet
        hwp.SetPos(0, para, 0)
        hwp.HAction.GetDefault("ParagraphShape", ps.HParaShape.HSet)
        orig = ps.HParaShape.AlignType
        set_para_field(hwp, para, "AlignType", 1)       # 왼쪽 정렬
        cols = [c for *_, c in scan_lines(hwp, para, with_text=False)]
        ref = ref_col if ref_col is not None else max(cols)
        return [ref - c for c in cols]
    except Exception as e:
        return f"<실패: {e}>"
    finally:
        if orig is not None:
            set_para_field(hwp, para, "AlignType", orig)


def m5_dry_run(hwp):
    """실제 알고리즘의 축소판 — 첫 문단을 위에서 아래로 한 줄씩 좁혀 본다."""
    log("\n" + "─" * 70)
    log("M5. 방식 A 예행 — 위에서 아래로 한 줄씩, 한도 안에서만")
    log("─" * 70)

    LIMITS = (-2, -4, -6, -8)          # 016 제안 한도 −8% 까지
    t0 = time.time()
    tries = 0
    para = 4
    before_n = len(scan_lines(hwp, para, with_text=False))
    before_slack = slack_by_left_align(hwp, para)
    log(f"  손대기 전 줄별 남는 칸(왼쪽 정렬로 재봄) = {before_slack}")
    line_idx = 0
    while line_idx < 20:
        lines = scan_lines(hwp, para, with_text=False)
        if line_idx >= len(lines) - 1:  # 마지막 줄은 손댈 이유가 없다
            break
        b, e = lines[line_idx][0], lines[line_idx][1]
        base_end = e[2]
        got = None
        for pct in LIMITS:
            apply_spacing(hwp, para, b[2], base_end, pct)
            tries += 1
            new = scan_lines(hwp, para, with_text=False)
            if len(new) <= line_idx:
                break
            if new[line_idx][1][2] > base_end:
                got = (pct, new[line_idx][1][2] - base_end)
                break
        if got is None:                 # 한도 안에서 안 되면 원래대로 두고 통과
            apply_spacing(hwp, para, b[2], base_end, 0)
            log(f"  줄{line_idx}: −8% 까지 좁혀도 당겨 올라오지 않음 → 그냥 둠")
        else:
            log(f"  줄{line_idx}: 자간 {got[0]}% 로 {got[1]}자 당겨 올림")
        line_idx += 1
    after_n = len(scan_lines(hwp, para, with_text=False))
    log(f"  손댄 뒤 줄별 남는 칸(왼쪽 정렬로 재봄) = {slack_by_left_align(hwp, para)}")
    log(f"\n  문단{para} 줄수 {before_n} → {after_n}, "
        f"자간 적용 시도 {tries}회, 걸린 시간 {time.time() - t0:.2f}s")
    log(f"  → 문단 하나에 {tries}회면 페이지 한 장(문단 20개 가정)에 "
        f"{tries * 20}회. 되돌리기 묶음·진행 표시가 반드시 필요한 규모인지 판단 근거.")


# ── M6. 비용과 예측 가능성 ───────────────────────────────
def m6_cost_and_formula(hwp):
    """더듬어 찾기(자간을 −2,−4,−6,−8 로 올려 보기)를 안 해도 되는지 본다.

    자간 p% 를 걸면 글자마다 폭이 p% 씩 줄고, 한글 한 글자는 2칸이므로
    줄에 n 글자가 있으면 이론상 2*n*p/100 칸이 빈다. 이게 맞으면 필요한 p 를
    **한 번에 계산**할 수 있어 시도 횟수가 1~2회로 줄어든다.
    """
    log("\n" + "─" * 70)
    log("M6. 비용 / 필요한 자간을 계산으로 맞힐 수 있는가")
    log("─" * 70)

    para = 1
    # 되돌려 깨끗한 상태에서 잰다
    ls = scan_lines(hwp, para, with_text=False)
    apply_spacing(hwp, para, ls[0][0][2], ls[-1][1][2], 0)

    log("\n[비용] COM 호출 100회씩 걸리는 시간")
    for label, fn in (
        ("GetPos", lambda: hwp.GetPos()),
        ("KeyIndicator", lambda: hwp.KeyIndicator()),
        ("MoveLineEnd", lambda: run(hwp, "MoveLineEnd")),
        ("한 줄 훑기(scan_lines 1문단)",
         lambda: scan_lines(hwp, para, with_text=False)),
    ):
        t0 = time.time()
        for _ in range(100):
            fn()
        log(f"  {label:28s} 100회 = {time.time() - t0:.2f}s "
            f"(1회 {(time.time() - t0) * 10:.1f}ms)")

    log("\n[예측] 자간 p% 를 걸면 첫 줄에 글자가 몇 개나 더 들어오는가")
    log("  (끝칸으로 재면 안 된다 — 좁히는 순간 줄이 다시 채워져 끝칸은 늘 꽉 찬 값이다.")
    log("   첫 실행에서 이걸로 헛measure 했다. 재야 할 것은 '줄에 담긴 글자 수'다.)")
    ls = scan_lines(hwp, para, with_text=False)
    b = ls[0][0]
    n0 = ls[0][1][2] - b[2]
    log(f"  기준: 문단{para} 첫 줄 {n0}자 (자간 0)")
    # 문단 전체에 걸어야 아래 줄 글자가 올라올 수 있다 — 첫 줄만 좁히면 재료가 없다
    tail = ls[-1][1][2]
    for p in (-2, -4, -6, -8, 2, 4):
        apply_spacing(hwp, para, b[2], tail, p)
        n = scan_lines(hwp, para, with_text=False)[0][1][2] - b[2]
        log(f"  자간 {p:+d}% → 첫 줄 {n}자 ({n - n0:+d}자), "
            f"이론값 {n0 / (1 + p / 100) - n0:+.1f}자")
        apply_spacing(hwp, para, b[2], tail, 0)
    log("  → 실측이 이론값에 가까우면 필요한 자간을 계산해 1~2회 만에 맞힐 수 있다.")


# ── 실행 ─────────────────────────────────────────────────
def main():
    hidden = "--hidden" in sys.argv
    keep = "--keep" in sys.argv
    log(f"자간 보정 스파이크 시작 (hidden={hidden}, keep={keep})")

    hwp = None
    try:
        hwp = spawn(hidden)
        fill_doc(hwp)
        log(f"문단 {len(PARAS)}개 삽입 완료")

        m0_inventory(hwp)
        lines = m1_line_select(hwp)
        m2_slack(hwp, lines)
        m3_spacing_scope(hwp)
        m4_reflow(hwp)
        m5_dry_run(hwp)
        m6_cost_and_formula(hwp)
    except Exception as e:
        import traceback
        log(f"\n✗ 스파이크 중단: {type(e).__name__}: {e}")
        log(traceback.format_exc())
    finally:
        if hwp is not None and not keep:
            try:
                # 저장하지 않고 버린다 — Clear(1) = '저장 안 함'
                hwp.XHwpDocuments.Item(0).Clear(1)
            except Exception as e:
                log(f"문서 버리기 실패(무시): {e}")
            try:
                hwp.Quit()
            except Exception as e:
                log(f"Quit 실패(무시): {e}")
            log("\n전용 한글 인스턴스를 닫았다 (저장 안 함)")
        log(f"\n로그: {LOG_PATH}")


if __name__ == "__main__":
    main()
