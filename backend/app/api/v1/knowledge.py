import hashlib
import uuid
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_tenant_id, require_roles
from app.db.models import (
    ConflictStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
    EmbeddingStatus,
    KnowledgeConflict,
    KnowledgeTestRun,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas import (
    DocumentChunkRead,
    DocumentRead,
    KnowledgeConflictRead,
    KnowledgeConflictUpdate,
    KnowledgeHealthResponse,
    KnowledgeRetrieveResponse,
    KnowledgeTestRequest,
    KnowledgeTestResponse,
    KnowledgeTestRunRead,
)
from app.services.audit import add_audit_log
from app.services.documents import ALLOWED_EXTENSIONS, document_path, process_document
from app.services.knowledge import KnowledgeService
from app.services.knowledge_health import knowledge_health, refresh_conflicts

router = APIRouter()
admin_dependency = require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)


def _get_document(db: Session, company_id: uuid.UUID, document_id: uuid.UUID) -> Document:
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.company_id == company_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/documents", response_model=list[DocumentRead], tags=["documents"])
def list_documents(
    company_id: uuid.UUID = Depends(get_tenant_id), db: Session = Depends(get_db)
) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(Document.company_id == company_id)
            .order_by(Document.created_at.desc())
        ).all()
    )


@router.post("/documents", response_model=DocumentRead, status_code=202, tags=["documents"])
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(admin_dependency),
    db: Session = Depends(get_db),
) -> Document:
    filename = Path(file.filename or "").name
    file_type = Path(filename).suffix.casefold()
    if not filename or file_type not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported formats: PDF, DOCX, TXT, CSV, and XLSX",
        )
    settings = get_settings()
    stored_name = f"{company_id}/{uuid.uuid4().hex}{file_type}"
    target = document_path(stored_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    persisted = False
    maximum = settings.document_max_size_mb * 1024 * 1024
    try:
        with target.open("xb") as stream:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > maximum:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Document must be {settings.document_max_size_mb} MB or smaller",
                    )
                digest.update(chunk)
                stream.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="Document is empty")
        sha256 = digest.hexdigest()
        if db.scalar(
            select(Document.id).where(Document.company_id == company_id, Document.sha256 == sha256)
        ):
            raise HTTPException(status_code=409, detail="This document was already uploaded")
        document = Document(
            company_id=company_id,
            uploaded_by_user_id=current_user.id,
            filename=filename,
            stored_name=stored_name,
            file_type=file_type,
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=size,
            sha256=sha256,
            status=DocumentStatus.UPLOADING,
            embedding_status=EmbeddingStatus.PENDING,
        )
        db.add(document)
        db.flush()
        add_audit_log(
            db,
            company_id=company_id,
            actor_user_id=current_user.id,
            action="DOCUMENT_UPLOADED",
            resource_type="document",
            resource_id=document.id,
            metadata={"filename": filename, "size_bytes": size},
        )
        db.commit()
        persisted = True
        db.refresh(document)
        background_tasks.add_task(process_document, document.id)
        return document
    except Exception:
        db.rollback()
        if target.exists() and not persisted:
            target.unlink()
        raise


@router.get("/documents/{document_id}", response_model=DocumentRead, tags=["documents"])
def get_document(
    document_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> Document:
    return _get_document(db, company_id, document_id)


@router.get(
    "/documents/{document_id}/chunks",
    response_model=list[DocumentChunkRead],
    tags=["documents"],
)
def list_document_chunks(
    document_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> list[DocumentChunk]:
    _get_document(db, company_id, document_id)
    return list(
        db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.company_id == company_id,
            )
            .order_by(DocumentChunk.chunk_index)
        ).all()
    )


@router.get("/documents/{document_id}/download", tags=["documents"])
def download_document(
    document_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> FileResponse:
    document = _get_document(db, company_id, document_id)
    path = document_path(document.stored_name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found")
    return FileResponse(path, media_type=document.mime_type, filename=document.filename)


@router.post("/documents/{document_id}/reprocess", response_model=DocumentRead, tags=["documents"])
def reprocess_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(admin_dependency),
    db: Session = Depends(get_db),
) -> Document:
    document = _get_document(db, company_id, document_id)
    document.status = DocumentStatus.UPLOADING
    document.embedding_status = EmbeddingStatus.PENDING
    document.error_message = None
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="DOCUMENT_REPROCESS_REQUESTED",
        resource_type="document",
        resource_id=document.id,
    )
    db.commit()
    db.refresh(document)
    background_tasks.add_task(process_document, document.id)
    return document


@router.delete("/documents/{document_id}", status_code=204, tags=["documents"])
def delete_document(
    document_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(admin_dependency),
    db: Session = Depends(get_db),
) -> None:
    document = _get_document(db, company_id, document_id)
    path = document_path(document.stored_name)
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="DOCUMENT_DELETED",
        resource_type="document",
        resource_id=document.id,
        metadata={"filename": document.filename},
    )
    db.execute(delete(Document).where(Document.id == document.id))
    db.commit()
    if path.exists():
        path.unlink()


@router.get("/knowledge/retrieve", response_model=KnowledgeRetrieveResponse, tags=["knowledge"])
def retrieve_knowledge(
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=20),
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> KnowledgeRetrieveResponse:
    sources, mode, vector_used = KnowledgeService(db, company_id).retrieve(q, limit)
    return KnowledgeRetrieveResponse(
        query=q,
        retrieval_mode=mode,
        embedding_available=vector_used,
        sources=sources,
    )


@router.post("/knowledge/test", response_model=KnowledgeTestResponse, tags=["knowledge"])
def test_knowledge(
    request: KnowledgeTestRequest,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeTestResponse:
    started = perf_counter()
    sources, mode, vector_used = KnowledgeService(db, company_id).retrieve(
        request.query, request.limit
    )
    source_ids = {source.source_id for source in sources}
    conflicts = (
        list(
            db.scalars(
                select(KnowledgeConflict).where(
                    KnowledgeConflict.company_id == company_id,
                    KnowledgeConflict.status == ConflictStatus.OPEN,
                    KnowledgeConflict.conflicting_source_id.in_(source_ids),
                )
            ).all()
        )
        if source_ids
        else []
    )
    if sources:
        top = sources[0]
        answer = f"Based on {top.title}: {top.content}"
        if conflicts:
            answer += " A conflicting secondary source was excluded in favor of structured data."
    else:
        answer = (
            "No grounded answer was found. Add or update knowledge before using this "
            "answer in a call."
        )
    latency = max(1, round((perf_counter() - started) * 1000))
    tools = list(dict.fromkeys(f"search_{source.source_type.lower()}" for source in sources))
    conflict_payload = [
        {"id": str(item.id), "summary": item.summary, "status": item.status.value}
        for item in conflicts
    ]
    source_payload = [source.model_dump(mode="json") for source in sources]
    run = KnowledgeTestRun(
        company_id=company_id,
        actor_user_id=current_user.id,
        query=request.query,
        answer_preview=answer,
        retrieval_latency_ms=latency,
        retrieval_mode=mode,
        tools_called=tools,
        sources_used=source_payload,
        conflicts_found=conflict_payload,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return KnowledgeTestResponse(
        id=run.id,
        query=request.query,
        answer_preview=answer,
        retrieved_knowledge=sources,
        tools_called=tools,
        retrieval_latency_ms=latency,
        records_used=len(sources),
        retrieval_mode=mode,
        conflicts=conflict_payload,
        embedding_available=vector_used,
        created_at=run.created_at,
    )


@router.get("/knowledge/test-runs", response_model=list[KnowledgeTestRunRead], tags=["knowledge"])
def list_test_runs(
    limit: int = Query(default=20, ge=1, le=100),
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> list[KnowledgeTestRun]:
    return list(
        db.scalars(
            select(KnowledgeTestRun)
            .where(KnowledgeTestRun.company_id == company_id)
            .order_by(KnowledgeTestRun.created_at.desc())
            .limit(limit)
        ).all()
    )


@router.get("/knowledge/health", response_model=KnowledgeHealthResponse, tags=["knowledge"])
def get_knowledge_health(
    company_id: uuid.UUID = Depends(get_tenant_id), db: Session = Depends(get_db)
) -> KnowledgeHealthResponse:
    response = knowledge_health(db, company_id)
    db.commit()
    return response


@router.get("/knowledge/conflicts", response_model=list[KnowledgeConflictRead], tags=["knowledge"])
def list_conflicts(
    company_id: uuid.UUID = Depends(get_tenant_id), db: Session = Depends(get_db)
) -> list[KnowledgeConflict]:
    return list(
        db.scalars(
            select(KnowledgeConflict)
            .where(KnowledgeConflict.company_id == company_id)
            .order_by(KnowledgeConflict.detected_at.desc())
        ).all()
    )


@router.post(
    "/knowledge/conflicts/refresh",
    response_model=list[KnowledgeConflictRead],
    tags=["knowledge"],
)
def refresh_knowledge_conflicts(
    company_id: uuid.UUID = Depends(get_tenant_id),
    _: User = Depends(admin_dependency),
    db: Session = Depends(get_db),
) -> list[KnowledgeConflict]:
    conflicts = refresh_conflicts(db, company_id)
    db.commit()
    return conflicts


@router.patch(
    "/knowledge/conflicts/{conflict_id}",
    response_model=KnowledgeConflictRead,
    tags=["knowledge"],
)
def update_conflict(
    conflict_id: uuid.UUID,
    request: KnowledgeConflictUpdate,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(admin_dependency),
    db: Session = Depends(get_db),
) -> KnowledgeConflict:
    conflict = db.scalar(
        select(KnowledgeConflict).where(
            KnowledgeConflict.id == conflict_id,
            KnowledgeConflict.company_id == company_id,
        )
    )
    if conflict is None:
        raise HTTPException(status_code=404, detail="Conflict not found")
    conflict.status = request.status
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="KNOWLEDGE_CONFLICT_UPDATED",
        resource_type="knowledge_conflict",
        resource_id=conflict.id,
        metadata={"status": request.status.value},
    )
    db.commit()
    db.refresh(conflict)
    return conflict
