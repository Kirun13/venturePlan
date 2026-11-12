"""Portable, Unicode-capable document exports from an immutable saved plan."""
import io
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

from app.schemas.models import BusinessPlan


def sections(plan: BusinessPlan):
    i, f, o = plan.idea, plan.finance, plan.operations
    yield "Business inputs", [
        ("text", i.description),
        ("table", [["Input", "Value"], ["Region", i.region], ["Audience", i.target_audience],
                   ["Budget", f"{i.initial_budget:,.2f} {i.currency}"],
                   ["Price per unit", f"{i.unit_price:,.2f} {i.currency}"],
                   ["Monthly units", str(i.estimated_monthly_units)]])]
    for label, result, text in (
        ("Market research", plan.market, plan.market.demand_summary),
        ("Competitor analysis", plan.competitors, plan.competitors.positioning)):
        content = [("text", text)]
        if hasattr(result, "competitors"):
            content += [("text", "Competitors: " + (", ".join(result.competitors) or "No substantiated competitors listed"))]
        content += [("bullet", "Assumption: " + value) for value in result.assumptions]
        content += [("text", "Sources are citations returned by the research provider; their presence does not independently verify every claim.")]
        details = {source.url: source for source in result.source_details}
        for url in result.sources:
            source = details.get(url)
            content.append(("text", f"{source.title if source else 'Source'}: {url}" +
                            (f" (retrieved {source.retrieved_at})" if source else "")))
        if not result.sources:
            content.append(("text", "No provider-cited sources. Treat the research as unverified assumptions."))
        yield label, content
    costs = [["Cost item", f"Amount {i.currency}"]]
    costs += [[item.name, f"{item.amount:,.2f}"] for item in o.startup_costs]
    monthly = [["Monthly fixed cost", f"Amount {i.currency}"]]
    monthly += [[item.name, f"{item.amount:,.2f}"] for item in o.monthly_fixed_costs]
    yield "Operations and launch", (
        [("bullet", step) for step in o.launch_steps] + [("table", costs), ("table", monthly)] +
        [("text", f"Variable cost per unit: {o.variable_cost_per_unit:,.2f} {i.currency}")] +
        [("bullet", "Staffing: " + value) for value in o.staffing] +
        [("bullet", "Estimate: " + value) for value in o.assumptions])
    rows = [["Financial measure", f"Value {i.currency}"]]
    for label, value in (("Monthly revenue", f.monthly_revenue), ("Monthly fixed costs", f.monthly_fixed_costs),
                         ("Monthly variable costs", f.monthly_variable_costs), ("Monthly profit", f.monthly_profit),
                         ("Startup costs", f.startup_costs), ("Budget gap", f.budget_gap)):
        rows.append([label, f"{value:,.2f}"])
    rows += [["Break even units", str(f.break_even_units) if f.break_even_units is not None else "Unavailable"],
             ["Payback months", str(f.payback_months) if f.payback_months is not None else "Unavailable"]]
    scenarios = [["Scenario", "Units", "Revenue", "Profit", "Payback months"]]
    scenarios += [[s.name, str(s.monthly_units), f"{s.monthly_revenue:,.0f}",
                   f"{s.monthly_profit:,.0f}", str(s.payback_months) if s.payback_months is not None else "Unavailable"]
                  for s in f.scenarios]
    yield "Financial model", [("table", rows), ("table", scenarios)] + [("bullet", v) for v in f.assumptions]
    v = plan.validation
    yield "Risks and validation", (
        [("text", "No blocking contradictions detected" if v.is_consistent else "Review required before using this plan"),
         ("text", f"Revision passes: {plan.revision_count}")] +
        [("bullet", "Issue: " + value) for value in v.issues] +
        [("bullet", "Risk: " + value) for value in v.risks] +
        [("bullet", "Warning: " + value) for value in v.warnings])
    yield "Evidence and assumptions", [
        ("text", "The business description, target audience, budget, unit price and sales forecast are user inputs."),
        ("text", "Operating costs and scenario volumes are estimates. Financial results are calculated from those inputs."),
        ("text", "This document is a draft. Taxes, financing costs, demand verification and launch timing need separate review.")]


def _pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = [
        (str(Path(__file__).parent / "assets/fonts/DejaVuSans.ttf"),
         str(Path(__file__).parent / "assets/fonts/DejaVuSans-Bold.ttf")),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf")]
    for normal, bold in candidates:
        if Path(normal).exists():
            if "VP" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("VP", normal))
                pdfmetrics.registerFont(TTFont("VPBold", bold))
                pdfmetrics.registerFontFamily("VP", normal="VP", bold="VPBold")
            return
    raise RuntimeError("Install DejaVu Sans fonts for Unicode PDF export")


def export_plan(raw: dict, format: str, version: int = 1, mode: str = "unknown"):
    plan = BusinessPlan.model_validate(raw)
    if format == "json":
        return json.dumps(raw, ensure_ascii=False, indent=2).encode(), "application/json"
    target = io.BytesIO()
    if format == "docx":
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        doc = Document()
        sec = doc.sections[0]
        sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
        sec.top_margin = sec.bottom_margin = Inches(0.8)
        sec.left_margin = sec.right_margin = Inches(0.8)
        normal = doc.styles["Normal"]
        normal.font.name = "Arial"
        normal.font.size = Pt(10)
        normal.paragraph_format.space_after = Pt(5)
        for style in ("Title", "Subtitle", "Heading 1", "Heading 2"):
            doc.styles[style].font.name = "Arial"
            doc.styles[style].font.color.rgb = RGBColor(0, 0, 0)
        doc.styles["Heading 1"].paragraph_format.space_before = Pt(14)
        doc.styles["Heading 1"].paragraph_format.space_after = Pt(8)
        for style in doc.styles:
            if style.style_id in ("Title", "Subtitle"):
                for border in list(style.element.iter(qn("w:pBdr"))):
                    border.getparent().remove(border)
        doc.add_paragraph("Business plan", style="Title")
        doc.add_paragraph(plan.idea.name, style="Subtitle")
        doc.add_paragraph(f"Draft version {version} | Research mode {mode}")
        doc.add_paragraph("This plan describes the proposed business, its assumptions, launch needs and financial scenarios.")
        for heading, content in sections(plan):
            doc.add_heading(heading, level=1)
            for item_index, (kind, value) in enumerate(content):
                if kind == "table":
                    table = doc.add_table(rows=0, cols=len(value[0]))
                    table.style = "Light Shading Accent 1"
                    look = table._tbl.tblPr.find(qn("w:tblLook"))
                    if look is not None:
                        look.set(qn("w:firstColumn"), "0")
                    for row_index, values in enumerate(value):
                        cells = table.add_row().cells
                        for cell, text in zip(cells, values):
                            cell.text = str(text)
                            props = cell._tc.get_or_add_tcPr()
                            margins = OxmlElement("w:tcMar")
                            for edge in ("top", "left", "bottom", "right"):
                                item = OxmlElement("w:"+edge)
                                item.set(qn("w:w"), "90")
                                item.set(qn("w:type"), "dxa")
                                margins.append(item)
                            props.append(margins)
                            for paragraph in cell.paragraphs:
                                paragraph.paragraph_format.space_after = Pt(2)
                                if len(value) <= 6 and row_index < len(value)-1:
                                    paragraph.paragraph_format.keep_with_next = True
                        table.rows[-1]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
                        if row_index == 0:
                            repeat = OxmlElement("w:tblHeader")
                            table.rows[-1]._tr.get_or_add_trPr().append(repeat)
                    doc.add_paragraph()
                else:
                    paragraph = doc.add_paragraph(value, style="List Bullet" if kind == "bullet" else "Normal")
                    if heading == "Evidence and assumptions" and item_index < len(content)-1:
                        paragraph.paragraph_format.keep_with_next = True
        footer = sec.footer.paragraphs[0]
        footer.alignment = 2
        footer.add_run("VenturePlan | ")
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        footer._p.append(field)
        doc.save(target)
        return target.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if format != "pdf":
        raise ValueError("Unsupported export format")
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    _pdf_font()
    styles = getSampleStyleSheet()
    body = ParagraphStyle("VPBody", fontName="VP", fontSize=9.5, leading=14, spaceAfter=7)
    title = ParagraphStyle("VPTitle", parent=body, fontName="VPBold", fontSize=24, leading=29, spaceAfter=12)
    heading = ParagraphStyle("VPHeading", parent=body, fontName="VPBold", fontSize=14, leading=19, spaceBefore=14, spaceAfter=9, keepWithNext=True)
    cell_style = ParagraphStyle("VPCell", parent=body, fontSize=8, leading=11, spaceAfter=0, splitLongWords=True)
    doc = SimpleDocTemplate(target, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48)
    story = [Paragraph("Business plan", title), Paragraph(escape(plan.idea.name), heading),
             Paragraph(f"Draft version {version} | Research mode {escape(mode)}", body),
             Paragraph("This plan describes the proposed business, its assumptions, launch needs and financial scenarios.", body)]
    for label, content in sections(plan):
        story.append(Paragraph(label, heading))
        for kind, value in content:
            if kind == "table":
                cells = [[Paragraph(escape(str(text)), cell_style) for text in row] for row in value]
                widths = [doc.width * 0.62, doc.width * 0.38] if len(value[0]) == 2 else [doc.width / len(value[0])] * len(value[0])
                table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf7")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#dce3ef")),
                ]))
                story.extend([KeepTogether([table]) if len(value) <= 6 else table, Spacer(1, 10)])
            else:
                story.append(Paragraph(("- " if kind == "bullet" else "") + escape(value), body))

    def footer(canvas, document):
        canvas.setFont("VP", 8)
        canvas.drawRightString(A4[0] - 48, 27, f"VenturePlan | {document.page}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return target.getvalue(), "application/pdf"
