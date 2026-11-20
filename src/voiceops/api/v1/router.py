from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.api.v1.dependencies import (
    get_current_user,
    require_roles,
    require_warehouse_access,
)
from voiceops.config import get_settings
from voiceops.core.security import create_access_token
from voiceops.database.connection import get_db
from voiceops.repositories.audit_logs import AuditRepository
from voiceops.repositories.products import ProductRepository
from voiceops.repositories.shipments import ShipmentRepository
from voiceops.repositories.users import UserRepository
from voiceops.repositories.warehouses import WarehouseRepository
from voiceops.schemas import (
    AuditLogResponse,
    InventoryResponse,
    OrderResponse,
    ProductResponse,
    ShipmentResponse,
    TransferOrderCreate,
    UserResponse,
    WarehouseResponse,
)
from voiceops.schemas.auth import LoginRequest, TokenResponse
from voiceops.services.audit import AuditService
from voiceops.services.auth import AuthService
from voiceops.services.exceptions import BusinessRuleError, NotFoundError
from voiceops.services.inventory import InventoryService
from voiceops.services.orders import OrderService

router = APIRouter(
    dependencies=[Depends(get_current_user)],
)

auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ---------------------------------------------------------------------------
# Response serialization helpers
# ---------------------------------------------------------------------------


def serialize_user(user: Any) -> dict[str, Any]:
    """Return public user fields without exposing the password hash."""
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def serialize_warehouse(warehouse: Any) -> dict[str, Any]:
    return {
        "id": warehouse.id,
        "name": warehouse.name,
        "code": warehouse.code,
        "address": warehouse.address,
        "city": warehouse.city,
        "state": warehouse.state,
        "is_active": warehouse.is_active,
        "created_at": warehouse.created_at,
        "updated_at": warehouse.updated_at,
    }


def serialize_product(product: Any) -> dict[str, Any]:
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "unit_of_measure": product.unit_of_measure,
        "is_active": product.is_active,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def serialize_inventory(item: Any) -> dict[str, Any]:
    return {
        "warehouse_id": item.warehouse_id,
        "product_id": item.product_id,
        "quantity_on_hand": item.quantity_on_hand,
        "quantity_reserved": item.quantity_reserved,
        "available_quantity": item.quantity_on_hand - item.quantity_reserved,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_shipment(shipment: Any) -> dict[str, Any]:
    return {
        "id": shipment.id,
        "shipment_number": shipment.shipment_number,
        "order_id": shipment.order_id,
        "status": shipment.status,
        "delivered_at": shipment.delivered_at,
        "received_at": shipment.received_at,
        "created_at": shipment.created_at,
        "updated_at": shipment.updated_at,
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@auth_router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
):
    """Authenticate a user, record the login, and return a JWT."""

    service = AuthService(session)

    user = await service.authenticate_user(
        email=str(payload.email),
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Record successful login.
    audit_service = AuditService(session)
    await audit_service.record_action(
        actor_user_id=user.id,
        action="login_succeeded",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email},
    )

    # Commit the audit record.
    await session.commit()

    settings = get_settings()

    access_token = create_access_token(
        subject=str(user.id),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
        "user": user,
    }


# ---------------------------------------------------------------------------
# Users - Admin only
# ---------------------------------------------------------------------------


@router.get(
    "/users",
    response_model=list[UserResponse],
    dependencies=[Depends(require_roles("admin"))],
)
async def list_users(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    repository = UserRepository(session)
    users = await repository.get_all(limit=limit, offset=offset)
    return [serialize_user(user) for user in users]


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_roles("admin"))],
)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repository = UserRepository(session)
    user = await repository.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return serialize_user(user)


# ---------------------------------------------------------------------------
# Warehouses
# ---------------------------------------------------------------------------


@router.get(
    "/warehouses",
    response_model=list[WarehouseResponse],
    dependencies=[Depends(require_roles("admin"))],
)
async def list_warehouses(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    repository = WarehouseRepository(session)
    warehouses = await repository.get_all(limit=limit, offset=offset)
    return [serialize_warehouse(warehouse) for warehouse in warehouses]


@router.get(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseResponse,
    dependencies=[Depends(require_warehouse_access)],
)
async def get_warehouse(
    warehouse_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repository = WarehouseRepository(session)
    warehouse = await repository.get_by_id(warehouse_id)

    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found.",
        )

    return serialize_warehouse(warehouse)


# ---------------------------------------------------------------------------
# Products - All authenticated roles can read
# ---------------------------------------------------------------------------


@router.get("/products", response_model=list[ProductResponse])
async def list_products(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    repository = ProductRepository(session)
    products = await repository.get_all(limit=limit, offset=offset)
    return [serialize_product(product) for product in products]


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repository = ProductRepository(session)
    product = await repository.get_by_id(product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    return serialize_product(product)


# ---------------------------------------------------------------------------
# Inventory - Warehouse assignment required
# ---------------------------------------------------------------------------


@router.get(
    "/inventory/{warehouse_id}",
    response_model=list[InventoryResponse],
    dependencies=[Depends(require_warehouse_access)],
)
async def list_warehouse_inventory(
    warehouse_id: UUID,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    warehouse_repository = WarehouseRepository(session)
    warehouse = await warehouse_repository.get_by_id(warehouse_id)

    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found.",
        )

    service = InventoryService(session)
    inventory = await service.list_warehouse_inventory(
        warehouse_id=warehouse_id,
        limit=limit,
        offset=offset,
    )

    return [serialize_inventory(item) for item in inventory]


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


@router.get("/orders/{order_number}", response_model=OrderResponse)
async def get_order(
    order_number: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = OrderService(session)

    try:
        return await service.get_order_details(order_number)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/orders/transfer",
    status_code=status.HTTP_201_CREATED,
    response_model=OrderResponse,
    dependencies=[Depends(require_roles("admin", "warehouse_manager", "operator"))],
)
async def create_transfer_order(
    payload: TransferOrderCreate,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = OrderService(session)

    try:
        order = await service.create_transfer_order(
            source_warehouse_id=payload.source_warehouse_id,
            destination_warehouse_id=payload.destination_warehouse_id,
            items=[item.model_dump() for item in payload.items],
            actor_user_id=current_user.id,
        )

        return await service.get_order_details(order.order_number)

    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except BusinessRuleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Audit Logs - Admin only
# ---------------------------------------------------------------------------


@router.get(
    "/audit-logs",
    response_model=list[AuditLogResponse],
    dependencies=[Depends(require_roles("admin"))],
)
async def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Return recent audit records. Accessible only to admins."""
    repository = AuditRepository(session)

    return await repository.get_recent(
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------


@router.get(
    "/shipments/{shipment_number}",
    response_model=ShipmentResponse,
)
async def get_shipment(
    shipment_number: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repository = ShipmentRepository(session)
    shipment = await repository.get_by_shipment_number(shipment_number)

    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found.",
        )

    return serialize_shipment(shipment)
