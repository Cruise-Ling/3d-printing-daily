# -*- coding: utf-8 -*-
"""极简 xlsx 生成器（零依赖）

为什么不用 openpyxl
------------------
本机未安装，且装包需要出网；而这个项目的所有产出都要求「零 CDN、零外部依赖」。
xlsx 本质是一个 zip 包 + 若干 XML，用标准库即可写出来。

支持：多 sheet、列宽、首行加粗、冻结首行、自动筛选、数字单元格（可排序求和）、
中文 inlineStr（不用 sharedStrings，牺牲体积换实现简单）。

不支持：样式主题、合并单元格、公式、图表、条件格式 —— 导出场景用不到。
"""
import io
import re
import zipfile

_ILLEGAL = re.compile(u"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MAX_CELL = 32767


def col_letter(n):
    """1 -> A, 27 -> AA"""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _esc(s):
    s = _ILLEGAL.sub("", s)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _cell(ref, value, style=0):
    if value is None:
        return ""
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (int, float)):
        return '<c r="%s" s="%d"><v>%s</v></c>' % (ref, style, value)
    text = _esc(str(value))[:_MAX_CELL]
    if not text:
        return ""
    return '<c r="%s" s="%d" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (
        ref, style, text)


def _sheet_xml(header, rows, widths, freeze=True, autofilter=True):
    ncol = max([len(header)] + [len(r) for r in rows]) if (header or rows) else 0
    nrow = (1 if header else 0) + len(rows)
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           '<dimension ref="A1:%s%d"/>' % (col_letter(max(ncol, 1)), max(nrow, 1))]

    if freeze:
        out.append('<sheetViews><sheetView workbookViewId="0">'
                   '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                   '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/>'
                   '</sheetView></sheetViews>')
    else:
        out.append('<sheetViews><sheetView workbookViewId="0"/></sheetViews>')

    out.append('<sheetFormatPr defaultRowHeight="15"/>')
    if widths:
        out.append("<cols>")
        for i, w in enumerate(widths[:ncol], 1):
            out.append('<col min="%d" max="%d" width="%s" customWidth="1"/>' % (i, i, w))
        out.append("</cols>")

    out.append("<sheetData>")
    r = 1
    if header:
        cells = "".join(_cell("%s%d" % (col_letter(i), r), h, 1)
                        for i, h in enumerate(header, 1))
        out.append('<row r="%d" ht="20" customHeight="1">%s</row>' % (r, cells))
        r += 1
    for row in rows:
        cells = "".join(_cell("%s%d" % (col_letter(i), r), v)
                        for i, v in enumerate(row, 1))
        out.append('<row r="%d">%s</row>' % (r, cells))
        r += 1
    out.append("</sheetData>")

    if autofilter and nrow > 1 and ncol:
        out.append('<autoFilter ref="A1:%s%d"/>' % (col_letter(ncol), nrow))
    out.append("</worksheet>")
    return "".join(out)


_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
%s
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2">
<font><sz val="10"/><color theme="1"/><name val="Microsoft YaHei"/></font>
<font><b/><sz val="10"/><color theme="1"/><name val="Microsoft YaHei"/></font>
</fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def save(path, sheets):
    """sheets: [{"name":str, "header":[...], "rows":[[...]], "widths":[...], "freeze":bool}]"""
    names, ct, wb, rels = [], [], [], []
    for i, sh in enumerate(sheets, 1):
        name = re.sub(r"[\[\]:*?/\\]", "", sh["name"])[:31] or ("Sheet%d" % i)
        names.append((name, i))
        ct.append('<Override PartName="/xl/worksheets/sheet%d.xml" '
                  'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % i)
        wb.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_esc(name), i, i))
        rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/'
                    'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i))

    sid = len(sheets) + 1
    rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/styles" Target="styles.xml"/>' % sid)

    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets>%s</sheets></workbook>' % "".join(wb))
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               '%s</Relationships>' % "".join(rels))

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _TYPES % "\n".join(ct))
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", _STYLES)
        for i, sh in enumerate(sheets, 1):
            z.writestr("xl/worksheets/sheet%d.xml" % i,
                       _sheet_xml(sh.get("header") or [], sh.get("rows") or [],
                                  sh.get("widths") or [], sh.get("freeze", True)))
    return path


if __name__ == "__main__":
    p = save("_xlsx_selftest.xlsx", [
        {"name": "帖子清单", "header": ["序号", "平台", "访问量"], "widths": [6, 12, 10],
         "rows": [[1, "YouTube", 12345], [2, "Reddit", None]]},
        {"name": "说明", "header": ["项", "值"], "widths": [20, 40],
         "rows": [["导出时间", "2026-11-20 15:00"]]},
    ])
    print("wrote", p, io.open(p, "rb").read(4))
