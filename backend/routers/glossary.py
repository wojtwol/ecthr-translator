"""Glossary management endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse, Response
from typing import List, Dict
from sqlalchemy.orm import Session
import uuid
from datetime import datetime
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from models.term import (
    Term,
    TermUpdate,
    TermStatus,
    GlossaryResponse,
    GlossaryStats,
    SourceReport,
    SourceReportItem,
)
from db.database import get_db
from db import models

router = APIRouter(prefix="/glossary", tags=["glossary"])


@router.get("/{document_id}", response_model=GlossaryResponse)
async def get_glossary(
    document_id: str,
    status: str = Query("all", description="Filter by status: all, pending, approved, edited, rejected"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get glossary terms for a document.

    Args:
        document_id: Document ID
        status: Filter by term status
        page: Page number
        per_page: Items per page
        db: Database session

    Returns:
        GlossaryResponse with terms and statistics
    """
    # Get all terms for this document from database
    query = db.query(models.Term).filter(models.Term.document_id == document_id)

    all_terms = query.all()

    # Calculate stats
    stats = GlossaryStats(
        total=len(all_terms),
        pending=len([t for t in all_terms if t.status == "pending"]),
        approved=len([t for t in all_terms if t.status == "approved"]),
        edited=len([t for t in all_terms if t.status == "edited"]),
        rejected=len([t for t in all_terms if t.status == "rejected"]),
        # Source breakdown
        from_hudoc=len([t for t in all_terms if t.source_type == "hudoc"]),
        from_curia=len([t for t in all_terms if t.source_type == "curia"]),
        from_iate=len([t for t in all_terms if t.source_type == "iate"]),
        from_tm_exact=len([t for t in all_terms if t.source_type == "tm_exact"]),
        from_tm_fuzzy=len([t for t in all_terms if t.source_type == "tm_fuzzy"]),
        from_proposed=len([t for t in all_terms if t.source_type == "proposed"]),
    )

    # FIXED: Create a NEW query for paginated results (don't reuse executed query)
    paginated_query = db.query(models.Term).filter(models.Term.document_id == document_id)

    # Filter by status if requested
    if status != "all":
        paginated_query = paginated_query.filter(models.Term.status == status)

    # Pagination
    doc_terms = paginated_query.offset((page - 1) * per_page).limit(per_page).all()

    # Convert DB models to Pydantic models
    terms_list = []
    for t in doc_terms:
        # Extract sources from references
        sources_list = []
        context = None
        if t.references and isinstance(t.references, dict):
            context = t.references.get("context")

            # Check for case_law_references (list of source objects from CaseLawResearcher)
            case_law_refs = t.references.get("case_law_references", [])
            if case_law_refs:
                for ref in case_law_refs:
                    if isinstance(ref, dict):
                        source_info = {
                            "source_type": ref.get("source", "unknown"),
                            "case_name": ref.get("case_name"),
                            "url": ref.get("url"),
                            "context": ref.get("context"),
                        }
                        sources_list.append(source_info)

        term_dict = {
            "id": t.id,
            "document_id": t.document_id,
            "source_term": t.source_term,
            "target_term": t.target_term,
            "original_proposal": t.original_proposal,
            "source_type": t.source_type,
            "confidence": t.confidence,
            "references": [],  # Database stores as dict, but Pydantic expects list - context extracted separately
            "status": t.status,
            "context": context,
            "sources": sources_list,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        terms_list.append(Term(**term_dict))

    return GlossaryResponse(
        total=query.count() if status != "all" else len(all_terms),
        stats=stats,
        terms=terms_list,
    )


@router.put("/{document_id}/{term_id}", response_model=Term)
async def update_term(document_id: str, term_id: str, update: TermUpdate, db: Session = Depends(get_db)):
    """
    Update a term (approve, edit, or reject).

    Args:
        document_id: Document ID
        term_id: Term ID
        update: Term update data
        db: Database session

    Returns:
        Updated term
    """
    # Find term in database
    term = db.query(models.Term).filter(
        models.Term.id == term_id,
        models.Term.document_id == document_id
    ).first()

    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    # Save original proposal if this is the first edit
    if term.original_proposal is None and update.status == TermStatus.EDITED:
        term.original_proposal = term.target_term

    # Update term
    term.target_term = update.target_term
    term.status = update.status.value
    term.updated_at = datetime.now()

    db.commit()
    db.refresh(term)

    # Extract sources from references
    sources_list = []
    context = None
    if term.references and isinstance(term.references, dict):
        context = term.references.get("context")

        # Check for case_law_references
        case_law_refs = term.references.get("case_law_references", [])
        if case_law_refs:
            for ref in case_law_refs:
                if isinstance(ref, dict):
                    source_info = {
                        "source_type": ref.get("source", "unknown"),
                        "case_name": ref.get("case_name"),
                        "url": ref.get("url"),
                        "context": ref.get("context"),
                    }
                    sources_list.append(source_info)

    return Term(
        id=term.id,
        document_id=term.document_id,
        source_term=term.source_term,
        target_term=term.target_term,
        original_proposal=term.original_proposal,
        source_type=term.source_type,
        confidence=term.confidence,
        references=[],  # Database stores as dict, but Pydantic expects list - context extracted separately
        status=term.status,
        context=context,
        sources=sources_list,
        created_at=term.created_at,
        updated_at=term.updated_at,
    )


@router.post("/{document_id}/approve-all")
async def approve_all_pending(document_id: str, db: Session = Depends(get_db)):
    """
    Approve all pending terms for a document.

    Args:
        document_id: Document ID
        db: Database session

    Returns:
        Count of approved terms
    """
    # Get all pending terms for this document
    pending_terms = db.query(models.Term).filter(
        models.Term.document_id == document_id,
        models.Term.status == "pending"
    ).all()

    count = 0
    for term in pending_terms:
        term.status = "approved"
        term.updated_at = datetime.now()
        count += 1

    db.commit()

    return {"message": f"Approved {count} terms", "count": count}


@router.get("/{document_id}/sources-report", response_model=SourceReport)
async def get_sources_report(document_id: str, db: Session = Depends(get_db)):
    """
    Get detailed report of term sources with case information.

    Args:
        document_id: Document ID
        db: Database session

    Returns:
        SourceReport with terms grouped by source type
    """
    # Get all terms for this document
    all_terms = db.query(models.Term).filter(
        models.Term.document_id == document_id
    ).all()

    # Helper function to extract case info from references
    def extract_case_info(references):
        if not references:
            return None, None, None

        if isinstance(references, dict):
            case_name = references.get("case_name")
            case_url = references.get("url")
            context = references.get("context")
            return case_name, case_url, context
        return None, None, None

    # Group terms by source type
    hudoc_terms = []
    curia_terms = []
    iate_terms = []
    tm_exact_terms = []
    tm_fuzzy_terms = []
    proposed_terms = []

    for t in all_terms:
        case_name, case_url, context = extract_case_info(t.references)

        item = SourceReportItem(
            source_term=t.source_term,
            target_term=t.target_term,
            source_type=t.source_type,
            case_name=case_name,
            case_url=case_url,
            context=context,
            status=t.status,
        )

        if t.source_type == "hudoc":
            hudoc_terms.append(item)
        elif t.source_type == "curia":
            curia_terms.append(item)
        elif t.source_type == "iate":
            iate_terms.append(item)
        elif t.source_type == "tm_exact":
            tm_exact_terms.append(item)
        elif t.source_type == "tm_fuzzy":
            tm_fuzzy_terms.append(item)
        elif t.source_type == "proposed":
            proposed_terms.append(item)

    return SourceReport(
        hudoc_terms=hudoc_terms,
        curia_terms=curia_terms,
        iate_terms=iate_terms,
        tm_exact_terms=tm_exact_terms,
        tm_fuzzy_terms=tm_fuzzy_terms,
        proposed_terms=proposed_terms,
    )


@router.get("/{document_id}/export/all/xlsx")
async def export_all_terms_xlsx(document_id: str, db: Session = Depends(get_db)):
    """
    Eksport wszystkich terminów do XLSX (przed zatwierdzeniem).

    Args:
        document_id: ID dokumentu
        db: Sesja bazy danych

    Returns:
        Plik XLSX ze wszystkimi terminami
    """
    # Sprawdź czy dokument istnieje
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Pobierz wszystkie terminy
    all_terms = db.query(models.Term).filter(
        models.Term.document_id == document_id
    ).order_by(models.Term.source_term).all()

    if not all_terms:
        raise HTTPException(status_code=404, detail="No terms found for this document")

    # Utwórz workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Glossary - All Terms"

    # Style dla nagłówka
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Style dla danych
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    cell_alignment = Alignment(vertical="top", wrap_text=True)

    # Header
    headers = ['Source Term (EN)', 'Target Term (PL)', 'Source Type', 'Status', 'Confidence', 'Case Name', 'Context']
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = border

    # Data rows
    for row_num, term in enumerate(all_terms, 2):
        case_name = ""
        context = ""

        if term.references and isinstance(term.references, dict):
            case_name = term.references.get("case_name", "")
            context = term.references.get("context", "")

        # Status color coding
        status_fill = None
        if term.status == "approved":
            status_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")  # Light green
        elif term.status == "edited":
            status_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")  # Light yellow
        elif term.status == "rejected":
            status_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")  # Light red

        data = [
            term.source_term,
            term.target_term or "",
            term.source_type,
            term.status,
            f"{term.confidence:.2f}",
            case_name,
            context
        ]

        for col_num, value in enumerate(data, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.border = border
            cell.alignment = cell_alignment

            # Apply status color to Status column
            if col_num == 4 and status_fill:
                cell.fill = status_fill

    # Adjust column widths
    ws.column_dimensions['A'].width = 30  # Source Term
    ws.column_dimensions['B'].width = 30  # Target Term
    ws.column_dimensions['C'].width = 15  # Source Type
    ws.column_dimensions['D'].width = 12  # Status
    ws.column_dimensions['E'].width = 12  # Confidence
    ws.column_dimensions['F'].width = 25  # Case Name
    ws.column_dimensions['G'].width = 50  # Context

    # Freeze header row
    ws.freeze_panes = 'A2'

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"glossary_all_{document_id}.xlsx"

    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/{document_id}/export/all/html")
async def export_all_terms_html(document_id: str, db: Session = Depends(get_db)):
    """
    Eksport wszystkich terminów do HTML (przed zatwierdzeniem).

    Args:
        document_id: ID dokumentu
        db: Sesja bazy danych

    Returns:
        Plik HTML ze wszystkimi terminami
    """
    # Sprawdź czy dokument istnieje
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Pobierz wszystkie terminy
    all_terms = db.query(models.Term).filter(
        models.Term.document_id == document_id
    ).order_by(models.Term.source_term).all()

    if not all_terms:
        raise HTTPException(status_code=404, detail="No terms found for this document")

    # Statystyki
    stats = {
        'total': len(all_terms),
        'approved': len([t for t in all_terms if t.status == 'approved']),
        'edited': len([t for t in all_terms if t.status == 'edited']),
        'pending': len([t for t in all_terms if t.status == 'pending']),
        'rejected': len([t for t in all_terms if t.status == 'rejected']),
    }

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Glossary - All Terms - {db_document.filename}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .meta {{
            color: #7f8c8d;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .stats {{
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .stat {{
            background: #ecf0f1;
            padding: 10px 20px;
            border-radius: 5px;
            font-size: 14px;
        }}
        .stat strong {{
            color: #2c3e50;
            font-size: 18px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 10px;
            border: 1px solid #ddd;
            vertical-align: top;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f0f8ff;
        }}
        .status-approved {{
            background-color: #d4edda !important;
            color: #155724;
            font-weight: 600;
        }}
        .status-edited {{
            background-color: #fff3cd !important;
            color: #856404;
            font-weight: 600;
        }}
        .status-pending {{
            background-color: #cce5ff !important;
            color: #004085;
        }}
        .status-rejected {{
            background-color: #f8d7da !important;
            color: #721c24;
        }}
        .source-type {{
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 3px;
            display: inline-block;
            background: #e9ecef;
        }}
        .confidence {{
            font-weight: 600;
            color: #27ae60;
        }}
        .context {{
            font-size: 12px;
            color: #555;
            max-width: 400px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Glossary - All Terms</h1>
        <div class="meta">
            <strong>Document:</strong> {db_document.filename}<br>
            <strong>Document ID:</strong> {document_id}<br>
            <strong>Exported:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>

        <div class="stats">
            <div class="stat">📊 <strong>{stats['total']}</strong> Total Terms</div>
            <div class="stat" style="background: #d4edda;">✓ <strong>{stats['approved']}</strong> Approved</div>
            <div class="stat" style="background: #fff3cd;">✏️ <strong>{stats['edited']}</strong> Edited</div>
            <div class="stat" style="background: #cce5ff;">⏳ <strong>{stats['pending']}</strong> Pending</div>
            <div class="stat" style="background: #f8d7da;">✗ <strong>{stats['rejected']}</strong> Rejected</div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 20%;">Source Term (EN)</th>
                    <th style="width: 20%;">Target Term (PL)</th>
                    <th style="width: 10%;">Source</th>
                    <th style="width: 8%;">Status</th>
                    <th style="width: 7%;">Confidence</th>
                    <th style="width: 15%;">Case Name</th>
                    <th style="width: 20%;">Context</th>
                </tr>
            </thead>
            <tbody>
"""

    # Data rows
    for term in all_terms:
        case_name = ""
        context = ""

        if term.references and isinstance(term.references, dict):
            case_name = term.references.get("case_name", "")
            context = term.references.get("context", "")

        status_class = f"status-{term.status}"

        html += f"""
                <tr>
                    <td><strong>{term.source_term}</strong></td>
                    <td>{term.target_term or '<em>-</em>'}</td>
                    <td><span class="source-type">{term.source_type}</span></td>
                    <td class="{status_class}">{term.status}</td>
                    <td class="confidence">{term.confidence:.2f}</td>
                    <td>{case_name or '<em>-</em>'}</td>
                    <td class="context">{context or '<em>-</em>'}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""

    filename = f"glossary_all_{document_id}.html"

    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/{document_id}/export/approved/xlsx")
async def export_approved_terms_xlsx(document_id: str, db: Session = Depends(get_db)):
    """
    Eksport tylko zatwierdzonych terminów do XLSX (po zatwierdzeniu).

    Args:
        document_id: ID dokumentu
        db: Sesja bazy danych

    Returns:
        Plik XLSX z zatwierdzonymi terminami
    """
    # Sprawdź czy dokument istnieje
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Pobierz tylko zatwierdzone terminy (approved + edited)
    approved_terms = db.query(models.Term).filter(
        models.Term.document_id == document_id,
        models.Term.status.in_(["approved", "edited"])
    ).order_by(models.Term.source_term).all()

    if not approved_terms:
        raise HTTPException(
            status_code=404,
            detail="No approved terms found for this document"
        )

    # Utwórz workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Glossary - Approved"

    # Style dla nagłówka
    header_fill = PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Style dla danych
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    cell_alignment = Alignment(vertical="top", wrap_text=True)

    # Header
    headers = ['Source Term (EN)', 'Target Term (PL)', 'Source Type', 'Status', 'Confidence', 'Original Proposal', 'Case Name', 'Context']
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = border

    # Data rows
    for row_num, term in enumerate(approved_terms, 2):
        case_name = ""
        context = ""

        if term.references and isinstance(term.references, dict):
            case_name = term.references.get("case_name", "")
            context = term.references.get("context", "")

        # Status color coding
        status_fill = None
        if term.status == "approved":
            status_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")  # Light green
        elif term.status == "edited":
            status_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")  # Light yellow

        data = [
            term.source_term,
            term.target_term or "",
            term.source_type,
            term.status,
            f"{term.confidence:.2f}",
            term.original_proposal or "",
            case_name,
            context
        ]

        for col_num, value in enumerate(data, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.border = border
            cell.alignment = cell_alignment

            # Apply status color to Status column
            if col_num == 4 and status_fill:
                cell.fill = status_fill

            # Highlight edited terms in Original Proposal column
            if col_num == 6 and value:  # Original Proposal column
                cell.fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
                cell.font = Font(italic=True, color="856404")

    # Adjust column widths
    ws.column_dimensions['A'].width = 30  # Source Term
    ws.column_dimensions['B'].width = 30  # Target Term
    ws.column_dimensions['C'].width = 15  # Source Type
    ws.column_dimensions['D'].width = 12  # Status
    ws.column_dimensions['E'].width = 12  # Confidence
    ws.column_dimensions['F'].width = 25  # Original Proposal
    ws.column_dimensions['G'].width = 25  # Case Name
    ws.column_dimensions['H'].width = 50  # Context

    # Freeze header row
    ws.freeze_panes = 'A2'

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"glossary_approved_{document_id}.xlsx"

    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/{document_id}/export/approved/html")
async def export_approved_terms_html(document_id: str, db: Session = Depends(get_db)):
    """
    Eksport tylko zatwierdzonych terminów do HTML (po zatwierdzeniu).

    Args:
        document_id: ID dokumentu
        db: Sesja bazy danych

    Returns:
        Plik HTML z zatwierdzonymi terminami
    """
    # Sprawdź czy dokument istnieje
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Pobierz tylko zatwierdzone terminy (approved + edited)
    approved_terms = db.query(models.Term).filter(
        models.Term.document_id == document_id,
        models.Term.status.in_(["approved", "edited"])
    ).order_by(models.Term.source_term).all()

    if not approved_terms:
        raise HTTPException(
            status_code=404,
            detail="No approved terms found for this document"
        )

    # Statystyki
    stats = {
        'total': len(approved_terms),
        'approved': len([t for t in approved_terms if t.status == 'approved']),
        'edited': len([t for t in approved_terms if t.status == 'edited']),
    }

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Glossary - Approved Terms - {db_document.filename}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #27ae60;
            border-bottom: 3px solid #27ae60;
            padding-bottom: 10px;
        }}
        .meta {{
            color: #7f8c8d;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .stats {{
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .stat {{
            background: #ecf0f1;
            padding: 10px 20px;
            border-radius: 5px;
            font-size: 14px;
        }}
        .stat strong {{
            color: #2c3e50;
            font-size: 18px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background-color: #27ae60;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 10px;
            border: 1px solid #ddd;
            vertical-align: top;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #e8f5e9;
        }}
        .status-approved {{
            background-color: #d4edda !important;
            color: #155724;
            font-weight: 600;
        }}
        .status-edited {{
            background-color: #fff3cd !important;
            color: #856404;
            font-weight: 600;
        }}
        .source-type {{
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 3px;
            display: inline-block;
            background: #e9ecef;
        }}
        .confidence {{
            font-weight: 600;
            color: #27ae60;
        }}
        .context {{
            font-size: 12px;
            color: #555;
            max-width: 400px;
        }}
        .original-proposal {{
            font-style: italic;
            color: #856404;
            background: #fff3cd;
            padding: 5px;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ Glossary - Approved Terms</h1>
        <div class="meta">
            <strong>Document:</strong> {db_document.filename}<br>
            <strong>Document ID:</strong> {document_id}<br>
            <strong>Exported:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>

        <div class="stats">
            <div class="stat">📊 <strong>{stats['total']}</strong> Approved Terms</div>
            <div class="stat" style="background: #d4edda;">✓ <strong>{stats['approved']}</strong> Approved (unchanged)</div>
            <div class="stat" style="background: #fff3cd;">✏️ <strong>{stats['edited']}</strong> Edited</div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 18%;">Source Term (EN)</th>
                    <th style="width: 18%;">Target Term (PL)</th>
                    <th style="width: 10%;">Source</th>
                    <th style="width: 8%;">Status</th>
                    <th style="width: 7%;">Confidence</th>
                    <th style="width: 14%;">Original Proposal</th>
                    <th style="width: 12%;">Case Name</th>
                    <th style="width: 13%;">Context</th>
                </tr>
            </thead>
            <tbody>
"""

    # Data rows
    for term in approved_terms:
        case_name = ""
        context = ""

        if term.references and isinstance(term.references, dict):
            case_name = term.references.get("case_name", "")
            context = term.references.get("context", "")

        status_class = f"status-{term.status}"
        original_proposal_html = ""
        if term.original_proposal:
            original_proposal_html = f'<span class="original-proposal">{term.original_proposal}</span>'

        html += f"""
                <tr>
                    <td><strong>{term.source_term}</strong></td>
                    <td><strong>{term.target_term or '<em>-</em>'}</strong></td>
                    <td><span class="source-type">{term.source_type}</span></td>
                    <td class="{status_class}">{term.status}</td>
                    <td class="confidence">{term.confidence:.2f}</td>
                    <td>{original_proposal_html or '<em>-</em>'}</td>
                    <td>{case_name or '<em>-</em>'}</td>
                    <td class="context">{context or '<em>-</em>'}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""

    filename = f"glossary_approved_{document_id}.html"

    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
