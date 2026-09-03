from __future__ import annotations

import re
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4
MARGIN = 50
BG = colors.HexColor("#F6F6F0")
INK = colors.HexColor("#171713")
MUTED = colors.HexColor("#74766F")
LIGHT_TEXT = colors.HexColor("#A4A69E")
LINE = colors.HexColor("#DEDED5")
LIME = colors.HexColor("#C8F04B")
GREEN = colors.HexColor("#719329")
SOFT = colors.HexColor("#EEF3DA")
WHITE = colors.white
LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "dcreation-logo.png"
WEBSITE_URL = "https://dcreationstudio.com/"
DISPLAY_WEBSITE = "dcreationstudio.com"
PHONE = "+91 9048292998"
EMAIL = "dcreationmarketing@gmail.com"


def _text(value: Any, fallback: str = "") -> str:
    clean = str(value or "").replace("\u2013", "-").replace("\u2014", "-")
    clean = clean.replace("\u00a0", " ").replace("\u2022", "-")
    return re.sub(r"[ \t]+", " ", clean).strip() or fallback


def _money(value: Any, currency: str = "INR") -> str:
    amount = float(value or 0)
    rendered = f"{amount:,.2f}".rstrip("0").rstrip(".")
    return f"{currency} {rendered}"


def _quantity(value: Any) -> str:
    number = float(value or 0)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _item_title(item: Any) -> str:
    return _text(getattr(item, "item_name", None), "Custom Service")


def proposal_display_title(items: Iterable[Any]) -> str:
    items = list(items)
    primary = _item_title(items[0]).lower() if items else "business growth"
    if "website" in primary or "web development" in primary or "ecommerce" in primary:
        return "Web Development"
    if "digital marketing" in primary or "social media" in primary:
        return "Digital Marketing"
    if "video" in primary:
        return "Video Production"
    if "branding" in primary or "brand identity" in primary:
        return "Branding"
    words = _item_title(items[0]).split()[:4] if items else ["Business", "Growth"]
    return " ".join(words)


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    paragraphs = _text(text).splitlines() or [""]
    lines: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if stringWidth(candidate, font, size) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _draw_wrapped(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    *,
    font: str = "Helvetica",
    size: float = 9,
    leading: float = 12,
    color: colors.Color = MUTED,
    max_lines: int | None = None,
) -> float:
    lines = _wrap(text, font, size, width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        final = lines[-1]
        while final and stringWidth(f"{final}...", font, size) > width:
            final = final[:-1]
        lines[-1] = f"{final.rstrip()}..."
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    for line in lines:
        pdf.drawString(x, y, line)
        y -= leading
    return y


def _section_label(pdf: canvas.Canvas, text: str, x: float, y: float) -> None:
    pdf.setStrokeColor(GREEN)
    pdf.setLineWidth(1.2)
    pdf.line(x, y + 2, x + 12, y + 2)
    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(x + 17, y, _text(text).upper())


def _brand_header(pdf: canvas.Canvas, section: str) -> None:
    pdf.setFillColor(INK)
    pdf.roundRect(MARGIN, PAGE_H - 72, 20, 20, 4, fill=1, stroke=0)
    pdf.setFillColor(LIME)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(MARGIN + 10, PAGE_H - 65.5, "D")
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(MARGIN + 28, PAGE_H - 65, "D CREATION ADVERTISEMENT COMPANY")
    pdf.setFillColor(LIGHT_TEXT)
    pdf.setFont("Helvetica-Bold", 6.5)
    pdf.drawRightString(PAGE_W - MARGIN, PAGE_H - 64, _text(section).upper())


def _corner(pdf: canvas.Canvas) -> None:
    pdf.setFillColor(INK)
    pdf.setStrokeColor(INK)
    path = pdf.beginPath()
    path.moveTo(PAGE_W - 71, 0)
    path.lineTo(PAGE_W, 71)
    path.lineTo(PAGE_W, 0)
    path.close()
    pdf.drawPath(path, fill=1, stroke=0)
    pdf.setFillColor(LIME)
    path = pdf.beginPath()
    path.moveTo(PAGE_W - 34, 0)
    path.lineTo(PAGE_W, 34)
    path.lineTo(PAGE_W, 0)
    path.close()
    pdf.drawPath(path, fill=1, stroke=0)


def _footer(pdf: canvas.Canvas, page_number: int, page_total: int = 10) -> None:
    pdf.setStrokeColor(LINE)
    pdf.setLineWidth(0.7)
    pdf.line(MARGIN, 47, PAGE_W - MARGIN - 30, 47)
    pdf.setFillColor(LIGHT_TEXT)
    pdf.setFont("Helvetica-Bold", 6.3)
    pdf.drawString(MARGIN, 29, "D CREATION ADVERTISEMENT COMPANY")
    if page_number not in {1, page_total}:
        pdf.drawRightString(PAGE_W - MARGIN - 35, 29, f"{page_number:02d} / {page_total:02d}")
    _corner(pdf)


def _new_page(pdf: canvas.Canvas, section: str, page_number: int) -> None:
    pdf.setFillColor(BG)
    pdf.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    _brand_header(pdf, section)
    _footer(pdf, page_number)


def _card(
    pdf: canvas.Canvas, x: float, y: float, w: float, h: float, *, fill: colors.Color = WHITE
) -> None:
    pdf.setFillColor(fill)
    pdf.setStrokeColor(LINE)
    pdf.setLineWidth(0.7)
    pdf.roundRect(x, y, w, h, 9, fill=1, stroke=1)


def _feature_lines(item: Any) -> list[str]:
    raw = _text(getattr(item, "description", None))
    if not raw:
        return ["Scope confirmed from the approved service package."]
    candidates = re.split(r"\n+|\s*[;|]\s*", raw)
    cleaned = [_text(value).lstrip("-* ") for value in candidates if _text(value)]
    return cleaned or [raw]


def _draw_cover(pdf: canvas.Canvas, proposal: Any, client: Any, title: str) -> None:
    _new_page(pdf, "Proposal Edition 2026", 1)
    _section_label(pdf, "Proposal Edition 2026", MARGIN, PAGE_H - 282)
    y = PAGE_H - 325
    for word in [*title.split(), "Proposal"]:
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 34)
        pdf.drawString(MARGIN, y, word)
        y -= 42
    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(MARGIN, y + 7, '"Vision into Reality"')
    pdf.setStrokeColor(GREEN)
    pdf.setLineWidth(2)
    pdf.line(MARGIN, y - 10, MARGIN + 48, y - 10)
    intro = (
        "A complete digital partnership - strategy, design, development and delivery "
        "built to turn your business vision into a measurable online experience."
    )
    _draw_wrapped(pdf, intro, MARGIN, 104, 355, size=8.2, leading=11, max_lines=3)
    pdf.setFillColor(LIGHT_TEXT)
    pdf.setFont("Helvetica-Bold", 6.2)
    pdf.drawString(PAGE_W - 163, 123, "PREPARED FOR")
    prepared_for = _text(getattr(client, "business_name", None)) or _text(client.name)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 10.5)
    pdf.drawString(PAGE_W - 163, 102, prepared_for)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7.2)
    pdf.drawString(PAGE_W - 163, 88, f"Proposal no. {_text(proposal.proposal_number)}")
    pdf.showPage()


def _draw_about(pdf: canvas.Canvas) -> None:
    _new_page(pdf, "About the Studio", 2)
    _section_label(pdf, "Who We Are", MARGIN, PAGE_H - 111)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawString(MARGIN, PAGE_H - 157, "Building brands that")
    pdf.drawString(MARGIN, PAGE_H - 187, "people remember.")
    left = (
        "D Creation Advertisement Company is built for founders and businesses "
        "who want their brand to look and perform bigger than their budget suggests. We "
        "combine design craft, content systems and performance advertising into one "
        "accountable team."
    )
    right = (
        "What began as a small creative desk has grown into a full-service studio serving retail, "
        "hospitality, real estate, education and personal brands across Kerala. Every "
        "plan is tailored "
        "to the client's category, audience and season - never a copy-paste template."
    )
    _draw_wrapped(pdf, left, MARGIN, PAGE_H - 213, 222, size=8.4, leading=12, max_lines=8)
    _draw_wrapped(pdf, right, 314, PAGE_H - 213, 230, size=8.4, leading=12, max_lines=8)
    for index, (heading, content) in enumerate(
        [
            (
                "Our Mission",
                "To make premium, strategy-led marketing accessible to every growing business.",
            ),
            (
                "Our Vision",
                "To be Kerala's most trusted creative-and-growth partner for ambitious businesses.",
            ),
        ]
    ):
        x = MARGIN + index * 247
        _card(pdf, x, 365, 232, 112)
        pdf.setFillColor(SOFT)
        pdf.roundRect(x + 13, 438, 29, 29, 8, fill=1, stroke=0)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawCentredString(x + 27.5, 447, "O" if index == 0 else "V")
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(x + 13, 421, heading)
        _draw_wrapped(pdf, content, x + 13, 403, 205, size=7.4, leading=10, max_lines=4)
    _section_label(pdf, "By the Numbers", MARGIN, 335)
    stats = [
        ("120+", "Happy Clients"),
        ("350+", "Projects Delivered"),
        ("5+", "Years of Craft"),
        ("98%", "Client Satisfaction"),
    ]
    for index, (value, caption) in enumerate(stats):
        x = MARGIN + index * 123
        _card(pdf, x, 245, 113, 72)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 19)
        pdf.drawString(x + 12, 277, value)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 6.8)
        pdf.drawString(x + 12, 260, caption)
    pdf.showPage()


def _draw_opportunity(pdf: canvas.Canvas, title: str) -> None:
    _new_page(pdf, f"Why {title}", 3)
    _section_label(pdf, "The Opportunity", MARGIN, PAGE_H - 111)
    heading = (
        "Your website should be\nyour strongest sales asset."
        if title == "Web Development"
        else "Your customers are\nalready online."
    )
    y = PAGE_H - 155
    for line in heading.splitlines():
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 24)
        pdf.drawString(MARGIN, y, line)
        y -= 29
    body = (
        "A professional website builds trust, explains your value and turns interest "
        "into enquiries - "
        "even while your office is closed."
        if title == "Web Development"
        else (
            "A focused digital presence places your brand where customers discover, "
            "compare and decide."
        )
    )
    _draw_wrapped(pdf, body, MARGIN, y - 2, 478, size=8.3, leading=11, max_lines=3)
    _section_label(pdf, "The Customer Journey", MARGIN, 553)
    _card(pdf, MARGIN, 437, 495, 98)
    journey = [
        ("01", "Discover"),
        ("02", "Explore"),
        ("03", "Trust"),
        ("04", "Enquire"),
        ("05", "Convert"),
    ]
    for index, (number, label) in enumerate(journey):
        cx = MARGIN + 50 + index * 98
        pdf.setFillColor(SOFT)
        pdf.roundRect(cx - 14, 491, 28, 28, 7, fill=1, stroke=0)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(cx, 500, number)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawCentredString(cx, 471, label)
        if index < 4:
            pdf.setStrokeColor(LINE)
            pdf.line(cx + 21, 505, cx + 77, 505)
    _section_label(pdf, "Why It Works", MARGIN, 401)
    reasons = [
        ("Always-On Presence", "Your business remains available to customers 24/7."),
        ("Built for Conversion", "Clear content and calls-to-action guide visitors to enquire."),
        ("Search Ready", "A clean structure helps search engines understand your services."),
        ("Easy to Grow", "The platform can expand as services, content and campaigns grow."),
    ]
    for index, (head, text) in enumerate(reasons):
        row = index % 2
        col = index // 2
        x = MARGIN + col * 252
        y = 335 - row * 72
        pdf.setFillColor(SOFT)
        pdf.roundRect(x, y, 30, 30, 8, fill=1, stroke=0)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(x + 15, y + 10, str(index + 1))
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 8.5)
        pdf.drawString(x + 42, y + 19, head)
        _draw_wrapped(pdf, text, x + 42, y + 5, 194, size=7.2, leading=9, max_lines=2)
    _section_label(pdf, "Delivery Timeline", MARGIN, 210)
    timeline = [
        ("01", "Discovery & scope"),
        ("02", "Design direction"),
        ("03", "Development"),
        ("04", "Review, test & launch"),
    ]
    for index, (step, label) in enumerate(timeline):
        x = MARGIN + index * 123
        _card(pdf, x, 116, 113, 72)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(x + 11, 163, step)
        _draw_wrapped(
            pdf,
            label,
            x + 11,
            144,
            91,
            font="Helvetica-Bold",
            size=7.5,
            leading=9,
            color=INK,
            max_lines=2,
        )
    pdf.showPage()


def _draw_services(pdf: canvas.Canvas) -> None:
    _new_page(pdf, "Our Services", 4)
    _section_label(pdf, "What We Do", MARGIN, PAGE_H - 111)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawString(MARGIN, PAGE_H - 155, "One studio.")
    pdf.drawString(MARGIN, PAGE_H - 185, "Every growth channel.")
    _draw_wrapped(
        pdf,
        "From first impression to final conversion - our services are built to work "
        "together, not in silos.",
        MARGIN,
        PAGE_H - 208,
        490,
        size=8.2,
        leading=11,
        max_lines=2,
    )
    services = [
        ("Social Media", "Strategy, content and management"),
        ("Brand Identity", "Systems that set you apart"),
        ("Website Development", "Fast, modern sites that convert"),
        ("SEO", "Rank higher and get found"),
        ("Meta Ads", "Facebook and Instagram campaigns"),
        ("Google Ads", "Search and display performance"),
        ("Video Production", "Reels, ads and brand films"),
        ("Photography", "Product and lifestyle shoots"),
        ("Drone Shoot", "Aerial visuals that stand out"),
        ("Event Coverage", "Full coverage, edited and delivered"),
    ]
    card_w, card_h = 93, 145
    for index, (name, detail) in enumerate(services):
        row, col = divmod(index, 5)
        x = MARGIN + col * 100
        y = 425 - row * 160
        _card(pdf, x, y, card_w, card_h)
        pdf.setFillColor(INK)
        pdf.roundRect(x + 12, y + card_h - 43, 29, 29, 7, fill=1, stroke=0)
        pdf.setFillColor(LIME)
        pdf.setFont("Helvetica-Bold", 7)
        initials = "".join(part[0] for part in name.split()[:2]).upper()
        pdf.drawCentredString(x + 26.5, y + card_h - 33, initials)
        _draw_wrapped(
            pdf,
            name,
            x + 12,
            y + card_h - 61,
            card_w - 24,
            font="Helvetica-Bold",
            size=7.9,
            leading=10,
            color=INK,
            max_lines=3,
        )
        _draw_wrapped(pdf, detail, x + 12, y + 48, card_w - 24, size=6.9, leading=9, max_lines=4)
    pdf.showPage()


def _draw_package(pdf: canvas.Canvas, proposal: Any, items: list[Any], title: str) -> None:
    _new_page(pdf, "Selected Package", 5)
    primary = items[0]
    _section_label(pdf, "Selected Plan", MARGIN, PAGE_H - 111)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 23)
    package_heading = _text(getattr(primary, "package_name", None))
    if not package_heading or package_heading.lower() == "custom service":
        package_heading = _item_title(primary)
    _draw_wrapped(
        pdf,
        package_heading,
        MARGIN,
        PAGE_H - 155,
        485,
        font="Helvetica-Bold",
        size=23,
        leading=27,
        color=INK,
        max_lines=2,
    )
    summary = _feature_lines(primary)[0]
    _draw_wrapped(pdf, summary, MARGIN, PAGE_H - 214, 485, size=8.4, leading=11, max_lines=3)
    pdf.setFillColor(INK)
    pdf.roundRect(MARGIN, 535, 495, 100, 10, fill=1, stroke=0)
    pdf.setFillColor(LIGHT_TEXT)
    pdf.setFont("Helvetica-Bold", 6.5)
    pdf.drawString(MARGIN + 35, 603, "APPROVED INVESTMENT")
    pdf.setFillColor(WHITE)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(MARGIN + 35, 560, _money(primary.amount, primary.currency))
    pdf.setFillColor(LIGHT_TEXT)
    pdf.setFont("Helvetica", 8)
    billing = "one-time package"
    pdf.drawString(MARGIN + 300, 562, billing)
    pdf.setFillColor(LIME)
    pdf.roundRect(PAGE_W - MARGIN - 64, 557, 39, 39, 9, fill=1, stroke=0)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(PAGE_W - MARGIN - 44.5, 570, "OK")
    _section_label(pdf, "What's Included", MARGIN, 505)
    features = _feature_lines(primary)
    if len(features) == 1:
        features.extend(
            [
                "Responsive layout for mobile and desktop",
                "Content-ready page structure",
                "Testing and launch support",
            ]
        )
    features = features[:8]
    for index, feature in enumerate(features[:4]):
        x = MARGIN + index * 123
        _card(pdf, x, 382, 113, 103)
        pdf.setFillColor(SOFT)
        pdf.roundRect(x + 37, 446, 38, 29, 8, fill=1, stroke=0)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(x + 56, 456, f"{index + 1:02d}")
        _draw_wrapped(
            pdf,
            feature,
            x + 11,
            425,
            91,
            font="Helvetica-Bold",
            size=7.1,
            leading=9,
            color=INK,
            max_lines=4,
        )
    _section_label(pdf, "Project Scope", MARGIN, 348)
    rows = features[4:] or [
        "Final scope follows the selected approved package and client requirements."
    ]
    if len(items) > 1:
        rows.extend(
            f"{_item_title(item)} - {_money(item.amount, item.currency)}" for item in items[1:]
        )
    rows = rows[:5]
    _card(pdf, MARGIN, 160, 495, 169)
    row_y = 302
    for index, row in enumerate(rows):
        if index:
            pdf.setStrokeColor(LINE)
            pdf.line(MARGIN + 20, row_y + 11, PAGE_W - MARGIN - 20, row_y + 11)
        pdf.setFillColor(SOFT)
        pdf.roundRect(MARGIN + 18, row_y - 6, 23, 23, 6, fill=1, stroke=0)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawCentredString(MARGIN + 29.5, row_y + 2, str(index + 1))
        _draw_wrapped(
            pdf,
            row,
            MARGIN + 55,
            row_y + 5,
            410,
            font="Helvetica-Bold",
            size=7.5,
            leading=9,
            color=INK,
            max_lines=2,
        )
        row_y -= 30
    pdf.showPage()


def _draw_investment(pdf: canvas.Canvas, proposal: Any, items: list[Any]) -> None:
    _new_page(pdf, "Investment & Scope", 6)
    _section_label(pdf, "Commercial Proposal", MARGIN, PAGE_H - 111)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawString(MARGIN, PAGE_H - 155, "Investment & scope")
    _draw_wrapped(
        pdf,
        "Approved package pricing captured from the knowledge base at the time this "
        "proposal was created.",
        MARGIN,
        PAGE_H - 180,
        488,
        size=8.2,
        leading=11,
        max_lines=2,
    )
    _card(pdf, MARGIN, 351, 495, 263)
    pdf.setFillColor(SOFT)
    pdf.roundRect(MARGIN + 12, 566, 471, 35, 7, fill=1, stroke=0)
    headers = [("SERVICE / PACKAGE", MARGIN + 25), ("QTY", 365), ("AMOUNT", 446)]
    for label, x in headers:
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(x, 580, label)
    row_y = 542
    visible_items = items[:7]
    for index, item in enumerate(visible_items):
        if index:
            pdf.setStrokeColor(LINE)
            pdf.line(MARGIN + 16, row_y + 14, PAGE_W - MARGIN - 16, row_y + 14)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(MARGIN + 25, row_y, _item_title(item)[:52])
        package = _text(getattr(item, "package_name", None))
        if package and package.lower() != "custom service":
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 6.8)
            pdf.drawString(MARGIN + 25, row_y - 12, package[:65])
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica", 8)
        pdf.drawRightString(397, row_y, _quantity(item.quantity))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawRightString(PAGE_W - MARGIN - 22, row_y, _money(item.amount, item.currency))
        row_y -= 38
    if len(items) > len(visible_items):
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica-Oblique", 7)
        pdf.drawString(
            MARGIN + 25,
            row_y,
            f"Plus {len(items) - len(visible_items)} additional approved line item(s).",
        )
    pdf.setFillColor(INK)
    pdf.roundRect(MARGIN, 286, 495, 49, 9, fill=1, stroke=0)
    pdf.setFillColor(LIGHT_TEXT)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(MARGIN + 22, 306, "TOTAL INVESTMENT")
    pdf.setFillColor(LIME)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawRightString(PAGE_W - MARGIN - 22, 301, _money(proposal.total_amount, proposal.currency))
    _section_label(pdf, "Proposal Details", MARGIN, 252)
    details = [
        ("Proposal date", proposal.proposal_date.strftime("%d %b %Y")),
        (
            "Valid until",
            proposal.valid_until.strftime("%d %b %Y")
            if proposal.valid_until
            else "7 days from proposal date",
        ),
        (
            "Project start",
            proposal.project_start_date.strftime("%d %b %Y")
            if getattr(proposal, "project_start_date", None)
            else "To be confirmed",
        ),
        (
            "Project end",
            proposal.project_end_date.strftime("%d %b %Y")
            if getattr(proposal, "project_end_date", None)
            else "As per final scope",
        ),
        ("Proposal number", _text(proposal.proposal_number)),
    ]
    for index, (label, value) in enumerate(details):
        x = MARGIN + index * 99
        _card(pdf, x, 180, 91, 53)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 6.7)
        pdf.drawString(x + 9, 215, label)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(x + 9, 197, value[:18])
    if _text(getattr(proposal, "notes", None)):
        _draw_wrapped(
            pdf, _text(proposal.notes), MARGIN, 151, 490, size=7.3, leading=9, max_lines=3
        )
    pdf.showPage()


def _draw_why(pdf: canvas.Canvas) -> None:
    _new_page(pdf, "Why Choose D Creation", 7)
    _section_label(pdf, "Why D Creation", MARGIN, PAGE_H - 111)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawString(MARGIN, PAGE_H - 155, "Reasons brands")
    pdf.drawString(MARGIN, PAGE_H - 185, "stay with us.")
    reasons = [
        ("Experienced Team", "Specialists across design, development, ads and video"),
        ("Fast Delivery", "Content and project turnaround within agreed timelines"),
        ("AI Workflow", "Faster production without cutting quality"),
        ("Premium Designs", "Every asset crafted to feel considered and high-end"),
        ("Dedicated Support", "A direct point of contact throughout the project"),
        ("ROI Focused", "Every digital decision connected to a business result"),
    ]
    for index, (heading, detail) in enumerate(reasons):
        row, col = divmod(index, 2)
        x = MARGIN + col * 250
        y = 581 - row * 90
        pdf.setFillColor(SOFT)
        pdf.roundRect(x, y, 31, 31, 8, fill=1, stroke=0)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(x + 15.5, y + 11, f"{index + 1:02d}")
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(x + 42, y + 19, heading)
        _draw_wrapped(pdf, detail, x + 42, y + 3, 192, size=7.2, leading=9, max_lines=3)
    pdf.showPage()


def _draw_terms(pdf: canvas.Canvas, proposal: Any) -> None:
    _new_page(pdf, "Terms & Conditions", 8)
    _section_label(pdf, "Terms & Conditions", MARGIN, PAGE_H - 111)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawString(MARGIN, PAGE_H - 155, "The fine print,")
    pdf.drawString(MARGIN, PAGE_H - 185, "kept simple.")
    agreed_terms = _text(
        getattr(proposal, "terms", None), "100% advance payment is required before project kickoff."
    )
    terms = [
        ("Payment", agreed_terms),
        (
            "Project Start",
            "Work begins after payment, scope confirmation and receipt of required client content.",
        ),
        (
            "Content & Access",
            "The client supplies approved copy, images, brand assets, logins and legal "
            "information on time.",
        ),
        (
            "Revisions",
            "Up to 3 reasonable revision rounds are included unless the selected "
            "package states otherwise.",
        ),
        (
            "Third-Party Costs",
            "Domain, hosting, paid plugins, ad spend, talent, travel and licensed assets "
            "are billed separately.",
        ),
        (
            "Scope Changes",
            "Work outside this proposal is quoted separately and starts only after "
            "written approval.",
        ),
    ]
    _card(pdf, MARGIN, 208, 495, 410)
    y = 574
    for index, (heading, detail) in enumerate(terms):
        if index:
            pdf.setStrokeColor(LINE)
            pdf.line(MARGIN + 20, y + 15, PAGE_W - MARGIN - 20, y + 15)
        pdf.setFillColor(SOFT)
        pdf.roundRect(MARGIN + 17, y - 8, 29, 29, 8, fill=1, stroke=0)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(MARGIN + 31.5, y + 2, str(index + 1))
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 8.8)
        pdf.drawString(MARGIN + 58, y + 8, heading)
        _draw_wrapped(pdf, detail, MARGIN + 58, y - 6, 402, size=7.1, leading=9, max_lines=3)
        y -= 64
    pdf.showPage()


def _draw_roadmap(pdf: canvas.Canvas, proposal: Any, title: str) -> None:
    _new_page(pdf, "Proposal Roadmap", 9)
    _section_label(pdf, "Delivery Roadmap", MARGIN, PAGE_H - 111)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawString(MARGIN, PAGE_H - 155, "A clear path from")
    pdf.drawString(MARGIN, PAGE_H - 185, "approval to launch.")
    _draw_wrapped(
        pdf,
        f"This {title.lower()} proposal follows a structured delivery process with clear "
        "review points, responsibilities and final handover.",
        MARGIN,
        PAGE_H - 214,
        485,
        size=8.3,
        leading=11,
        max_lines=3,
    )

    start_date = getattr(proposal, "project_start_date", None)
    end_date = getattr(proposal, "project_end_date", None)
    _card(pdf, MARGIN, 544, 495, 72, fill=INK)
    schedule = [
        ("PLANNED START", start_date.strftime("%d %b %Y") if start_date else "TO BE CONFIRMED"),
        ("TARGET COMPLETION", end_date.strftime("%d %b %Y") if end_date else "AS PER FINAL SCOPE"),
        ("DOCUMENT TYPE", "CLIENT PROPOSAL"),
    ]
    for index, (label, value) in enumerate(schedule):
        x = MARGIN + 24 + index * 160
        pdf.setFillColor(LIGHT_TEXT)
        pdf.setFont("Helvetica-Bold", 6.1)
        pdf.drawString(x, 589, label)
        pdf.setFillColor(LIME if index == 2 else WHITE)
        pdf.setFont("Helvetica-Bold", 8.5)
        pdf.drawString(x, 566, value[:24])

    steps = [
        ("Discovery & kickoff", "Confirm goals, audience, scope, access and project owners."),
        ("Strategy & structure", "Approve the delivery plan, content structure and priorities."),
        ("Creative production", "Design and produce the approved package deliverables."),
        ("Review & refinement", "Collect consolidated feedback and complete included revisions."),
        ("Final delivery & launch", "Complete quality checks, handover and agreed launch support."),
    ]
    _section_label(pdf, "Working Process", MARGIN, 513)
    y = 448
    for index, (heading, detail) in enumerate(steps):
        pdf.setFillColor(SOFT)
        pdf.roundRect(MARGIN, y, 46, 46, 12, fill=1, stroke=0)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(MARGIN + 23, y + 18, f"{index + 1:02d}")
        if index < len(steps) - 1:
            pdf.setStrokeColor(LINE)
            pdf.setLineWidth(1.2)
            pdf.line(MARGIN + 23, y, MARGIN + 23, y - 25)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(MARGIN + 66, y + 29, heading)
        _draw_wrapped(
            pdf,
            detail,
            MARGIN + 66,
            y + 12,
            420,
            size=7.5,
            leading=9,
            max_lines=2,
        )
        y -= 71
    pdf.showPage()


def _draw_qr(pdf: canvas.Canvas, value: str, x: float, y: float, size: float) -> None:
    widget = qr.QrCodeWidget(value)
    x1, y1, x2, y2 = widget.getBounds()
    width, height = x2 - x1, y2 - y1
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, pdf, x, y)


def _draw_contact(pdf: canvas.Canvas, client: Any, title: str) -> None:
    _new_page(pdf, "Thank You", 10)
    pdf.setFillColor(SOFT)
    pdf.roundRect(PAGE_W / 2 - 55, 637, 110, 22, 11, fill=1, stroke=0)
    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica-Bold", 6.5)
    pdf.drawCentredString(PAGE_W / 2, 645, "LET'S GET STARTED")
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 27)
    pdf.drawCentredString(PAGE_W / 2, 594, "Let's Build")
    pdf.setFillColor(GREEN)
    pdf.drawCentredString(PAGE_W / 2, 560, "Your Vision")
    client_name = _text(getattr(client, "business_name", None)) or _text(client.name)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(PAGE_W / 2, 535, f"Prepared for {client_name} - {title} Proposal")
    _card(pdf, 157, 334, 115, 115)
    _draw_qr(pdf, WEBSITE_URL, 171, 348, 87)
    contacts = [
        ("WEBSITE", DISPLAY_WEBSITE),
        ("PHONE", PHONE),
        ("EMAIL", EMAIL),
    ]
    y = 421
    for index, (label, value) in enumerate(contacts):
        pdf.setFillColor(SOFT)
        pdf.roundRect(303, y - 17, 30, 30, 8, fill=1, stroke=0)
        pdf.setFillColor(GREEN)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawCentredString(318, y - 6, ["W", "P", "E"][index])
        pdf.setFillColor(LIGHT_TEXT)
        pdf.setFont("Helvetica-Bold", 5.8)
        pdf.drawString(345, y + 3, label)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(345, y - 11, value)
        y -= 55
    pdf.showPage()


def build_proposal_pdf(
    *,
    proposal: Any,
    client: Any,
    company: Any,
    items: list[Any],
    logo_path: Path | None = None,
) -> bytes:
    """Render a tenant-scoped, immutable proposal as a ten-page client brochure."""
    del company, logo_path
    if not items:
        raise ValueError("A proposal requires at least one line item")
    output = BytesIO()
    title = proposal_display_title(items)
    prepared_for = _text(getattr(client, "business_name", None)) or _text(client.name)
    pdf = canvas.Canvas(output, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"{prepared_for} - {title} Proposal")
    pdf.setAuthor("D Creation Advertisement Company")
    pdf.setSubject(f"Professional {title.lower()} proposal")
    _draw_cover(pdf, proposal, client, title)
    _draw_about(pdf)
    _draw_opportunity(pdf, title)
    _draw_services(pdf)
    _draw_package(pdf, proposal, items, title)
    _draw_investment(pdf, proposal, items)
    _draw_why(pdf)
    _draw_terms(pdf, proposal)
    _draw_roadmap(pdf, proposal, title)
    _draw_contact(pdf, client, title)
    pdf.save()
    return output.getvalue()
