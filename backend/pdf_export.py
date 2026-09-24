import os
import re
import html
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

EXPLORER_URL = os.getenv("EXPLORER_URL", "https://scan.bohr.life")
NETWORK_NAME = os.getenv("NETWORK_NAME", "BOT Chain Testnet")

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page numbers in footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#94a3b8"))
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(40, 36, letter[0] - 40, 36)
        
        self.drawString(40, 24, "Tugas · Decentralized Proof of Learning · Anchored on BOT Chain")
        self.drawRightString(letter[0] - 40, 24, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def _sanitize(text: str | None) -> str:
    if not text:
        return ""
    escaped = html.escape(text.strip())
    return escaped.replace("\n", "<br/>")


def generate_milestone_pdf(branch: dict, subject: dict, milestones: list[dict], user_wallet: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=16,
        textColor=colors.HexColor("#1e1b4b"),
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "MilestoneBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8,
    )

    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )

    meta_val = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )

    badge_style = ParagraphStyle(
        "Badge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0d9488"),
    )

    story = []

    # --- Header Banner ---
    banner_data = [
        [
            Paragraph("<b>TUGAS</b>", ParagraphStyle("Brand", fontName="Helvetica-Bold", fontSize=18, leading=20, textColor=colors.HexColor("#7c3aed"))),
            Paragraph("PROOF OF LEARNING DOSSIER", ParagraphStyle("BannerTag", fontName="Helvetica-Bold", fontSize=9, leading=11, alignment=2, textColor=colors.HexColor("#6d28d9"))),
        ]
    ]
    banner_table = Table(banner_data, colWidths=[200, letter[0] - 280])
    banner_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#7c3aed"), spaceAfter=14))

    # --- Title & Details ---
    branch_title = branch.get("title") or "Coursework Assignment"
    subject_name = subject.get("name") or "Subject"
    kind_label = (branch.get("kind") or "Assignment").capitalize()

    story.append(Paragraph(f"{branch_title}", title_style))
    story.append(Paragraph(f"Subject: <b>{html.escape(subject_name)}</b> &nbsp;|&nbsp; Type: <b>{kind_label}</b> &nbsp;|&nbsp; Certified on: <b>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</b>", subtitle_style))

    # --- Verification Summary Box ---
    anchored_count = sum(1 for m in milestones if m.get("tx_hash"))
    total_count = len(milestones)
    status_text = f"ALL {total_count} MILESTONES ANCHORED & VERIFIED" if anchored_count == total_count and total_count > 0 else f"{anchored_count} OF {total_count} MILESTONES ANCHORED"
    status_color = "#0d9488" if anchored_count == total_count else "#d97706"

    summary_data = [
        [
            Paragraph("<b>Student Wallet:</b>", meta_label),
            Paragraph(html.escape(user_wallet or "Anonymous"), meta_val),
        ],
        [
            Paragraph("<b>Network:</b>", meta_label),
            Paragraph(f"{NETWORK_NAME} (Keccak-256)", meta_val),
        ],
        [
            Paragraph("<b>Ledger Status:</b>", meta_label),
            Paragraph(f"<font color='{status_color}'><b>{status_text}</b></font>", meta_label),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[100, letter[0] - 180])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#edf2f7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # --- Milestones Section ---
    story.append(Paragraph("<b>Submitted Milestones & On-Chain Commitments</b>", ParagraphStyle(
        "SectionHeader", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor("#0f172a"), spaceAfter=10
    )))

    for i, m in enumerate(milestones):
        milestone_elements = []
        m_title = m.get("title") or f"Milestone #{i+1}"
        m_draft = m.get("draft_text") or "(No draft content submitted)"
        tx_hash = m.get("tx_hash")
        work_hash = m.get("work_hash")
        ai_level = m.get("ai_assist_level", 60)
        commit_id = m.get("chain_commit_id")

        header_text = f"<b>{i+1}. {html.escape(m_title)}</b>"
        badge_text = "<b>✔ Anchored on-chain</b>" if tx_hash else "<i>Pending on-chain commit</i>"
        badge_color = "#0d9488" if tx_hash else "#94a3b8"

        header_table = Table(
            [[
                Paragraph(header_text, section_heading),
                Paragraph(f"<font color='{badge_color}'>{badge_text}</font>", ParagraphStyle("BadgeAlign", parent=badge_style, alignment=2))
            ]],
            colWidths=[letter[0] - 220, 140]
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        milestone_elements.append(header_table)
        milestone_elements.append(Spacer(1, 4))

        draft_p = Paragraph(_sanitize(m_draft), body_style)
        draft_table = Table([[draft_p]], colWidths=[letter[0] - 80])
        draft_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        milestone_elements.append(draft_table)
        milestone_elements.append(Spacer(1, 4))

        if tx_hash:
            explorer_link = f"{EXPLORER_URL}/tx/{tx_hash}"
            proof_rows = [
                [
                    Paragraph("<b>Work Hash (Keccak256):</b>", meta_label),
                    Paragraph(html.escape(work_hash or "-"), meta_val),
                ],
                [
                    Paragraph("<b>Tx Hash:</b>", meta_label),
                    Paragraph(f"<a href='{explorer_link}' color='#6d28d9'><u>{html.escape(tx_hash)}</u></a>", meta_val),
                ],
            ]
            if commit_id is not None:
                proof_rows.append([
                    Paragraph("<b>Chain Commit ID:</b>", meta_label),
                    Paragraph(f"#{commit_id} &nbsp;|&nbsp; AI Assist Declared: {ai_level}%", meta_val),
                ])
            proof_table = Table(proof_rows, colWidths=[140, letter[0] - 220])
            proof_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            milestone_elements.append(proof_table)

        milestone_elements.append(Spacer(1, 14))
        story.append(KeepTogether(milestone_elements))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
