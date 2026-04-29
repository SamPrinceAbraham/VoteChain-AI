"""
pdf_gen.py – Generate a vote confirmation PDF receipt using ReportLab.
Privacy rule: Candidate name is NOT included.
"""
import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# ── Colour palette ────────────────────────────────────────────────────────────
PURPLE   = colors.HexColor("#6C63FF")
DARK     = colors.HexColor("#1a1a2e")
LIGHT_BG = colors.HexColor("#f5f5ff")
GREEN    = colors.HexColor("#00B894")
GREY     = colors.HexColor("#888888")
WHITE    = colors.white


def _mask_voter_id(voter_id: str) -> str:
    """e.g.  VOTER001 → VOT***01"""
    if len(voter_id) <= 4:
        return voter_id[:1] + "***"
    return voter_id[:3] + "***" + voter_id[-2:]


def generate_receipt(voter_id: str, voter_name: str, constituency: str,
                     block_hash: str, block_index: int,
                     timestamp: str) -> bytes:
    """
    Generate a vote-confirmation PDF and return the raw bytes.
    Returns bytes so Flask can stream it directly via send_file(io.BytesIO(...)).
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2.5*cm, rightMargin=2.5*cm)

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle("Title2", parent=styles["Title"],
                                 textColor=PURPLE, fontSize=22,
                                 spaceAfter=4, alignment=TA_CENTER)
    sub_style   = ParagraphStyle("Sub", parent=styles["Normal"],
                                 textColor=GREY, fontSize=9,
                                 alignment=TA_CENTER)
    label_style = ParagraphStyle("Label", parent=styles["Normal"],
                                 textColor=DARK, fontSize=10, fontName="Helvetica-Bold")
    value_style = ParagraphStyle("Value", parent=styles["Normal"],
                                 textColor=colors.black, fontSize=10)
    hash_style  = ParagraphStyle("Hash", parent=styles["Normal"],
                                 textColor=PURPLE, fontSize=7,
                                 fontName="Courier", wordWrap="CJK")
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"],
                                  textColor=GREY, fontSize=8, alignment=TA_CENTER)
    warn_style   = ParagraphStyle("Warn", parent=styles["Normal"],
                                  textColor=GREEN, fontSize=9,
                                  alignment=TA_CENTER, fontName="Helvetica-Bold")

    elements = []

    # ── Header ────────────────────────────────────────────────────────────────
    elements.append(Paragraph("⛓️ VoteChain AI", title_style))
    elements.append(Paragraph("Smart Blockchain-Based Secure Voting System", sub_style))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(HRFlowable(width="100%", thickness=2, color=PURPLE))
    elements.append(Spacer(1, 0.4*cm))

    elements.append(Paragraph("✅ VOTE CONFIRMATION RECEIPT", ParagraphStyle(
        "BigGreen", parent=styles["Normal"], textColor=GREEN,
        fontSize=16, fontName="Helvetica-Bold", alignment=TA_CENTER
    )))
    elements.append(Spacer(1, 0.5*cm))

    # ── Details table ─────────────────────────────────────────────────────────
    receipt_data = [
        [Paragraph("Voter Name", label_style),       Paragraph(voter_name, value_style)],
        [Paragraph("Masked Voter ID", label_style),  Paragraph(_mask_voter_id(voter_id), value_style)],
        [Paragraph("Constituency", label_style),     Paragraph(constituency, value_style)],
        [Paragraph("Block Number", label_style),     Paragraph(f"#{block_index}", value_style)],
        [Paragraph("Timestamp (UTC)", label_style),  Paragraph(timestamp, value_style)],
        [Paragraph("Voting Status", label_style),    Paragraph("✅ Vote Successfully Recorded", ParagraphStyle(
            "GreenVal", parent=styles["Normal"], textColor=GREEN,
            fontSize=10, fontName="Helvetica-Bold"
        ))],
    ]

    tbl = Table(receipt_data, colWidths=[5*cm, 11*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BG),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [WHITE, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ddddee")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.5*cm))

    # ── Transaction hash ──────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(Paragraph("Transaction / Block Hash", label_style))
    elements.append(Spacer(1, 0.1*cm))
    elements.append(Paragraph(block_hash, hash_style))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY))

    # ── Privacy notice ────────────────────────────────────────────────────────
    elements.append(Spacer(1, 0.4*cm))
    elements.append(Paragraph(
        "🔒 Your vote choice is kept confidential. "
        "This receipt confirms your participation only.",
        warn_style
    ))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(Paragraph(
        "This document is generated automatically. No candidate name is disclosed to protect voter anonymity. "
        "The transaction hash above uniquely identifies your vote on the blockchain.",
        footer_style
    ))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(HRFlowable(width="100%", thickness=2, color=PURPLE))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph(
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}  |  VoteChain AI © 2024",
        footer_style
    ))

    doc.build(elements)
    return buf.getvalue()
