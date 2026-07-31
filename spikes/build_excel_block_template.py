# -*- coding: utf-8 -*-
r"""문항 엑셀 '덩어리 틀'(.xlsm) 굽기 — **엑셀 COM 으로 한 번만** 만든다.

왜 이 파일이 있나 (2026-07-31):
    사용자 결정 "형태 B — 진짜 버튼(xlsm + 매크로)로 구현". 그런데 버튼과
    VBA 가 든 파일은 openpyxl 로 **만들 수 없다** — vbaProject.bin 은 엑셀만
    구울 수 있는 바이너리다. 그래서 여기서 엑셀을 COM 으로 부려 틀을 한 번
    굽고, 그 결과물(assets/excel_block_template.xlsm)을 저장소에 담아 둔다.
    내보내기(excel_blocks.build_xlsm)는 이 틀을 복사해 꾸러미 목록만 채운다.

    조건: 엑셀 설치 + "VBA 프로젝트 개체 모델에 대한 액세스 허용" (실측
    2026-07-31: 이 컴퓨터는 둘 다 충족). 꺼져 있으면 엑셀 옵션 → 보안 센터 →
    매크로 설정에서 켜야 한다 — 이 스크립트를 다시 돌릴 일이 있을 때만.

실행:  python spikes\build_excel_block_template.py
"""

import pathlib
import sys

import win32com.client

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "excel_block_template.xlsm"

# 시트 이름 — excel_blocks.py 와 맞춘 약속 (바꾸면 양쪽을 함께)
SHEET_MAIN = "시험지"
SHEET_PACKS = "_꾸러미"

# VBA — 덩어리 추가 단추 하나가 전부다. 목록·마크다운은 프로그램(파이썬)이
# 맡는다: VBA 를 키우면 학교 PC 마다 디버깅할 길이 없어진다.
VBA = r'''
Sub 덩어리추가()
    Dim ws As Worksheet, hid As Worksheet
    Dim nm As String, slots As String
    Dim i As Long, r As Long
    Set ws = ThisWorkbook.Worksheets("시험지")
    Set hid = ThisWorkbook.Worksheets("_꾸러미")
    nm = CStr(ws.Range("B1").Value)
    If nm = "" Then
        MsgBox "B1 드롭다운에서 꾸러미를 먼저 고르세요.", vbInformation, "문항 엑셀"
        Exit Sub
    End If
    For i = 2 To hid.Cells(hid.Rows.Count, 1).End(xlUp).Row
        If CStr(hid.Cells(i, 1).Value) = nm Then slots = CStr(hid.Cells(i, 2).Value)
    Next i
    If slots = "" Then
        MsgBox "꾸러미를 찾지 못했습니다: " & nm, vbExclamation, "문항 엑셀"
        Exit Sub
    End If
    Dim arr() As String
    arr = Split(slots, ",")
    r = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row + 2
    If r < 4 Then r = 4
    ' 머리줄 — 읽기(파이썬)가 이 표시(▶ )로 덩어리를 찾는다
    ws.Cells(r, 1).Value = ChrW(9654) & " " & nm
    ws.Cells(r, 1).Font.Bold = True
    ws.Range(ws.Cells(r, 1), ws.Cells(r, 2)).Interior.Color = RGB(234, 243, 255)
    For i = 0 To UBound(arr)
        ws.Cells(r + 1 + i, 1).Value = Trim$(arr(i))
        ws.Cells(r + 1 + i, 1).Font.Color = RGB(87, 96, 106)
        With ws.Range(ws.Cells(r + 1 + i, 1), ws.Cells(r + 1 + i, 2)).Borders
            .LineStyle = 1
            .Color = RGB(208, 215, 222)
        End With
    Next i
    ws.Cells(r + 1, 2).Select
End Sub
'''


def main():
    xl = win32com.client.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        wb = xl.Workbooks.Add()
        while wb.Worksheets.Count > 1:
            wb.Worksheets(wb.Worksheets.Count).Delete()
        ws = wb.Worksheets(1)
        ws.Name = SHEET_MAIN

        ws.Range("A1").Value = "꾸러미 고르기 →"
        ws.Range("A1").Font.Bold = True
        ws.Range("B1").Interior.Color = 0xFFF7EA        # BGR — 옅은 파랑
        ws.Range("A2").Value = ("고른 뒤 [＋ 덩어리 추가]를 누르면 아래에 칸이 "
                                "생깁니다. 값(B열)만 채우세요. 빈칸은 '-'.")
        ws.Range("A2").Font.Color = 0x6A6057            # BGR — 흐린 회색
        ws.Columns("A").ColumnWidth = 16
        ws.Columns("B").ColumnWidth = 64

        hid = wb.Worksheets.Add(After=ws)
        hid.Name = SHEET_PACKS
        hid.Range("A1").Value = "이름"
        hid.Range("B1").Value = "빈칸이름들(콤마)"
        hid.Visible = 0                                 # xlSheetHidden

        # 단추 — 시트 위 폼 컨트롤. 매크로 이름만 이어 주면 된다.
        btn = ws.Buttons().Add(210, 4, 110, 24)
        btn.Text = "＋ 덩어리 추가"
        btn.OnAction = "덩어리추가"

        mod = wb.VBProject.VBComponents.Add(1)          # vbext_ct_StdModule
        mod.CodeModule.AddFromString(VBA)

        OUT.parent.mkdir(parents=True, exist_ok=True)
        if OUT.exists():
            OUT.unlink()
        wb.SaveAs(str(OUT), FileFormat=52)              # xlOpenXMLWorkbookMacroEnabled
        wb.Close(False)
        print("구웠습니다:", OUT)
    finally:
        xl.Quit()


if __name__ == "__main__":
    sys.exit(main())
