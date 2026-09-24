import os
import re
from io import BytesIO
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

EXPLORER_URL = os.getenv("EXPLORER_URL", "https://scan.bohr.life")
NETWORK_NAME = os.getenv("NETWORK_NAME", "BOT Chain Testnet")

def _set_cell_background(cell, hex_color: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tc_pr.append(shd)

def generate_milestone_docx(branch: dict, subject: dict, milestones: list[dict], user_wallet: str) -> bytes:
    doc = Document()

    # Set standard 1-inch margins
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.8)
        s.right_margin = Inches(0.8)

    # Document Header / Brand
    brand_p = doc.add_paragraph()
    brand_run = brand_p.add_run("TUGAS  ·  PROOF OF LEARNING DOSSIER")
    brand_run.font.name = "Arial"
    brand_run.font.size = Pt(9.5)
    brand_run.font.bold = True
    brand_run.font.color.rgb = RGBColor(124, 58, 237) # Purple
    brand_p.paragraph_format.space_after = Pt(4)

    # Assignment Title
    branch_title = branch.get("title") or "Coursework Assignment"
    title_p = doc.add_paragraph()
    title_run = title_p.add_run(branch_title)
    title_run.font.name = "Arial"
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(15, 23, 42)
    title_p.paragraph_format.space_after = Pt(2)

    # Subtitle
    subject_name = subject.get("name") or "Subject"
    kind_label = (branch.get("kind") or "Assignment").capitalize()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    sub_p = doc.add_paragraph()
    sub_run = sub_p.add_run(f"Subject: {subject_name}   |   Type: {kind_label}   |   Certified: {now_str}")
    sub_run.font.name = "Arial"
    sub_run.font.size = Pt(10)
    sub_run.font.color.rgb = RGBColor(100, 116, 139)
    sub_p.paragraph_format.space_after = Pt(14)

    # Metadata & Verification Table
    anchored_count = sum(1 for m in milestones if m.get("tx_hash"))
    total_count = len(milestones)
    status_text = f"ALL {total_count} MILESTONES ANCHORED & VERIFIED" if anchored_count == total_count and total_count > 0 else f"{anchored_count} OF {total_count} MILESTONES ANCHORED"

    meta_table = doc.add_table(rows=3, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False

    labels = ["Student Wallet:", "Network:", "Ledger Status:"]
    values = [user_wallet or "Anonymous", f"{NETWORK_NAME} (Keccak-256)", status_text]

    for i in range(3):
        row = meta_table.rows[i]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(1.8)
        c1.width = Inches(5.0)
        _set_cell_background(c0, "F8FAFC")
        _set_cell_background(c1, "F8FAFC")

        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_before = Pt(3)
        p0.paragraph_format.space_after = Pt(3)
        r0 = p0.add_run(labels[i])
        r0.font.name = "Arial"
        r0.font.bold = True
        r0.font.size = Pt(9)
        r0.font.color.rgb = RGBColor(71, 85, 105)

        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_before = Pt(3)
        p1.paragraph_format.space_after = Pt(3)
        r1 = p1.add_run(values[i])
        r1.font.name = "Courier New" if i != 2 else "Arial"
        r1.font.size = Pt(8.5) if i != 2 else Pt(9)
        if i == 2:
            r1.font.bold = True
            r1.font.color.rgb = RGBColor(13, 148, 136) if anchored_count == total_count else RGBColor(217, 119, 6)
        else:
            r1.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # Section Heading
    sec_head_p = doc.add_paragraph()
    sec_head_run = sec_head_p.add_run("Submitted Milestones & On-Chain Commitments")
    sec_head_run.font.name = "Arial"
    sec_head_run.font.size = Pt(13)
    sec_head_run.font.bold = True
    sec_head_run.font.color.rgb = RGBColor(30, 27, 75)
    sec_head_p.paragraph_format.space_after = Pt(10)

    # Milestones Loop
    for idx, m in enumerate(milestones):
        m_title = m.get("title") or f"Milestone #{idx+1}"
        m_draft = m.get("draft_text") or "(No draft content submitted)"
        tx_hash = m.get("tx_hash")
        work_hash = m.get("work_hash")
        ai_level = m.get("ai_assist_level", 60)
        commit_id = m.get("chain_commit_id")

        # Milestone Heading
        m_head_p = doc.add_paragraph()
        m_head_run = m_head_p.add_run(f"{idx+1}. {m_title}")
        m_head_run.font.name = "Arial"
        m_head_run.font.size = Pt(12)
        m_head_run.font.bold = True
        m_head_run.font.color.rgb = RGBColor(15, 23, 42)

        badge_run = m_head_p.add_run("   [✔ Anchored on BOT Chain]" if tx_hash else "   [Pending commit]")
        badge_run.font.name = "Arial"
        badge_run.font.size = Pt(9)
        badge_run.font.bold = True
        badge_run.font.color.rgb = RGBColor(13, 148, 136) if tx_hash else RGBColor(148, 163, 184)
        m_head_p.paragraph_format.space_after = Pt(4)

        # Draft Text in callout table
        draft_table = doc.add_table(rows=1, cols=1)
        draft_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        draft_cell = draft_table.rows[0].cells[0]
        draft_cell.width = Inches(6.8)
        _set_cell_background(draft_cell, "FFFFFF")

        dp = draft_cell.paragraphs[0]
        dp.paragraph_format.space_before = Pt(6)
        dp.paragraph_format.space_after = Pt(6)
        d_run = dp.add_run(m_draft)
        d_run.font.name = "Arial"
        d_run.font.size = Pt(10)
        d_run.font.color.rgb = RGBColor(51, 65, 85)

        # Proof Table if anchored
        if tx_hash:
            proof_table = doc.add_table(rows=3 if commit_id is not None else 2, cols=2)
            proof_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            proof_rows = [
                ("Work Hash (Keccak256):", work_hash or "-"),
                ("Transaction Hash:", tx_hash),
            ]
            if commit_id is not None:
                proof_rows.append(("Chain Commit ID:", f"#{commit_id}   |   AI Assist Level: {ai_level}%"))

            for p_idx, (k, v) in enumerate(proof_rows):
                p_row = proof_table.rows[p_idx]
                pc0, pc1 = p_row.cells[0], p_row.cells[1]
                pc0.width = Inches(2.0)
                pc1.width = Inches(4.8)
                _set_cell_background(pc0, "F1F5F9")
                _set_cell_background(pc1, "F1F5F9")

                pk_p = pc0.paragraphs[0]
                pk_p.paragraph_format.space_before = Pt(2)
                pk_p.paragraph_format.space_after = Pt(2)
                pkr = pk_p.add_run(k)
                pkr.font.name = "Arial"
                pkr.font.bold = True
                pkr.font.size = Pt(8)
                pkr.font.color.rgb = RGBColor(71, 85, 105)

                pv_p = pc1.paragraphs[0]
                pv_p.paragraph_format.space_before = Pt(2)
                pv_p.paragraph_format.space_after = Pt(2)
                pvr = pv_p.add_run(v)
                pvr.font.name = "Courier New"
                pvr.font.size = Pt(7.5)
                pvr.font.color.rgb = RGBColor(109, 40, 217)

        # Space between milestones
        sep_p = doc.add_paragraph()
        sep_p.paragraph_format.space_after = Pt(10)

    # Footer note
    footer = doc.sections[0].footer
    footer_p = footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    f_run = footer_p.add_run("Tugas · Cryptographically Verified on BOT Chain")
    f_run.font.name = "Arial"
    f_run.font.size = Pt(8)
    f_run.font.color.rgb = RGBColor(148, 163, 184)

    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()
