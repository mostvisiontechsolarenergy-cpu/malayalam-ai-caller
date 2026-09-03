import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_id, require_roles
from app.db.models import User, UserRole
from app.db.session import get_db
from app.services.audit import add_audit_log

Validator = Callable[[Session, uuid.UUID, dict[str, Any], Any | None], None]
FilterFactory = Callable[[type], list]
tenant_writer = require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)


def create_crud_router(
    *,
    prefix: str,
    tag: str,
    model: type,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    validator: Validator | None = None,
    current_filter: FilterFactory | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    resource_name = model.__name__.upper()

    @router.post("", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    def create_resource(
        payload: create_schema,  # type: ignore[valid-type]
        company_id: uuid.UUID = Depends(get_tenant_id),
        current_user: User = Depends(tenant_writer),
        db: Session = Depends(get_db),
    ):
        data = payload.model_dump()
        if validator:
            validator(db, company_id, data, None)
        resource = model(company_id=company_id, **data)
        db.add(resource)
        db.flush()
        add_audit_log(
            db,
            company_id=company_id,
            actor_user_id=current_user.id,
            action="CREATE",
            resource_type=resource_name,
            resource_id=resource.id,
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"{model.__name__} conflicts with existing data",
            ) from exc
        db.refresh(resource)
        return resource

    @router.get("", response_model=list[read_schema])
    def list_resources(
        company_id: uuid.UUID = Depends(get_tenant_id),
        db: Session = Depends(get_db),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=100),
        current_only: bool = Query(default=False),
    ):
        statement = select(model).where(model.company_id == company_id)
        if current_only and current_filter:
            statement = statement.where(*current_filter(model))
        statement = statement.order_by(model.created_at.desc()).offset(offset).limit(limit)
        return list(db.scalars(statement).all())

    @router.get("/{resource_id}", response_model=read_schema)
    def get_resource(
        resource_id: uuid.UUID,
        company_id: uuid.UUID = Depends(get_tenant_id),
        db: Session = Depends(get_db),
    ):
        resource = db.scalar(
            select(model).where(model.id == resource_id, model.company_id == company_id)
        )
        if resource is None:
            raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
        return resource

    @router.patch("/{resource_id}", response_model=read_schema)
    def update_resource(
        resource_id: uuid.UUID,
        payload: update_schema,  # type: ignore[valid-type]
        company_id: uuid.UUID = Depends(get_tenant_id),
        current_user: User = Depends(tenant_writer),
        db: Session = Depends(get_db),
    ):
        resource = db.scalar(
            select(model).where(model.id == resource_id, model.company_id == company_id)
        )
        if resource is None:
            raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return resource
        if validator:
            validator(db, company_id, data, resource)
        for key, value in data.items():
            setattr(resource, key, value)
        add_audit_log(
            db,
            company_id=company_id,
            actor_user_id=current_user.id,
            action="UPDATE",
            resource_type=resource_name,
            resource_id=resource.id,
            metadata={"fields": sorted(data)},
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409, detail=f"{model.__name__} update conflict"
            ) from exc
        db.refresh(resource)
        return resource

    @router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_resource(
        resource_id: uuid.UUID,
        company_id: uuid.UUID = Depends(get_tenant_id),
        current_user: User = Depends(tenant_writer),
        db: Session = Depends(get_db),
    ) -> Response:
        resource = db.scalar(
            select(model).where(model.id == resource_id, model.company_id == company_id)
        )
        if resource is None:
            raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
        add_audit_log(
            db,
            company_id=company_id,
            actor_user_id=current_user.id,
            action="DELETE",
            resource_type=resource_name,
            resource_id=resource.id,
        )
        db.delete(resource)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Resource is referenced and cannot be deleted",
            ) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
