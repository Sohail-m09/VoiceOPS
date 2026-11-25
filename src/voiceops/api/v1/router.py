import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastmcp import Client
from google import genai
from google.genai.errors import ServerError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.agents.context_resolver import resolve_conversation_request
from voiceops.agents.graph import build_agent_graph
from voiceops.agents.state import create_initial_state
from voiceops.api.v1.dependencies import (
    get_current_user,
    require_roles,
    require_warehouse_access,
)
from voiceops.config import get_settings
from voiceops.core.security import create_access_token
from voiceops.database.connection import get_db
from voiceops.database.models.user_warehouse import UserWarehouse
from voiceops.harness.context_manager import ContextManager
from voiceops.mcp.server import create_mcp_server
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
from voiceops.schemas.chat import ChatRequest, ChatResponse
from voiceops.services.audit import AuditService
from voiceops.services.auth import AuthService
from voiceops.services.conversations import (
    create_conversation,
    get_conversation_history,
    save_conversation_message,
)
from voiceops.services.exceptions import BusinessRuleError, NotFoundError
from voiceops.services.inventory import InventoryService
from voiceops.services.orders import OrderService

logger = logging.getLogger(__name__)
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB
router = APIRouter(
    dependencies=[Depends(get_current_user)],
)

auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)



async def transcribe_audio(
    *,
    audio_bytes: bytes,
    mime_type: str,
) -> str:
    """Transcribe uploaded audio using Gemini 3.5 Transcribe."""

    settings = get_settings()

    if settings.gemini_api_key is None:
        raise RuntimeError("Gemini API key is not configured.")

    def generate_transcript() -> str:
        client = genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options={"api_version": "v1beta"},
        )

        temporary_path = None
        uploaded_file = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            ) as temporary_file:
                temporary_file.write(audio_bytes)
                temporary_path = temporary_file.name

            uploaded_file = client.files.upload(
                file=temporary_path,
            )

            interaction = client.interactions.create(
                model=settings.gemini_audio_model,
                input=[
                    {
                        "type": "audio",
                        "uri": uploaded_file.uri,
                        "mime_type": uploaded_file.mime_type or mime_type,
                    }
                ],
                generation_config={
                    "transcription_config": {
                        "mode": "verbatim",
                    }
                },
            )

            return interaction.output_text

        finally:
            if uploaded_file is not None:
                try:
                    client.files.delete(name=uploaded_file.name)
                except Exception:
                    logging.warning(
                        "Could not delete temporary Gemini audio file.",
                    )

            if temporary_path is not None:
                Path(temporary_path).unlink(missing_ok=True)

    transcript = await asyncio.to_thread(generate_transcript)

    if not isinstance(transcript, str) or not transcript.strip():
        raise RuntimeError("Gemini returned an empty transcription.")

    return transcript.strip()



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

# ---------------------------------------------------------------------------
# Text Chat - Authenticated users
# ---------------------------------------------------------------------------


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(
    payload: ChatRequest,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Process an authenticated message within a stored conversation."""

    try:
        # ---------------------------------------------------------
        # 1. Create or retrieve the user's conversation
        # ---------------------------------------------------------

        if payload.conversation_id is None:
            conversation = await create_conversation(
                session=session,
                user_id=current_user.id,
                title=payload.message[:200],
            )

            conversation_id = conversation.id

            conversation_history = []

        else:
            conversation_id = payload.conversation_id

            # This function also verifies conversation ownership.
            previous_messages = await get_conversation_history(
                session=session,
                conversation_id=conversation_id,
                user_id=current_user.id,
                limit=20,
            )

            conversation_history = [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in previous_messages
            ]

        # ---------------------------------------------------------
        # 2. Load trusted warehouse access from PostgreSQL
        # ---------------------------------------------------------

        warehouse_ids = ()

        if current_user.role != "admin":
            result = await session.scalars(
                select(UserWarehouse.warehouse_id).where(
                    UserWarehouse.user_id == current_user.id
                )
            )

            warehouse_ids = tuple(result.all())

        # ---------------------------------------------------------
        # 3. Create the execution context
        # ---------------------------------------------------------

        context = ContextManager.create_context(
            user_id=current_user.id,
            user_role=current_user.role,
            warehouse_ids=warehouse_ids,
            request_text=payload.message,
            conversation_id=conversation_id,
            metadata={"source": "streamlit_chat"},
        )

        # ---------------------------------------------------------
        # 4. Persist the user's message before agent execution
        # ---------------------------------------------------------

        await save_conversation_message(
            session=session,
            conversation_id=conversation_id,
            user_id=current_user.id,
            request_id=context.request_id,
            role="user",
            content=payload.message,
        )

        # Commit before external Gemini/MCP operations.
        await session.commit()

        # ---------------------------------------------------------
        # 5. Resolve the message using previous conversation history
        # ---------------------------------------------------------

        resolution = await resolve_conversation_request(
            current_message=payload.message,
            conversation_history=conversation_history,
        )

        if resolution["needs_clarification"]:
            clarification = resolution["clarification_question"]

            await save_conversation_message(
                session=session,
                conversation_id=conversation_id,
                user_id=current_user.id,
                request_id=context.request_id,
                role="assistant",
                content=clarification,
            )

            await session.commit()

            return ChatResponse(
                request_id=context.request_id,
                conversation_id=conversation_id,
                status="not_required",
                answer=clarification,
                clarification_required=True,
                agent_results=[],
                evidence=[],
                errors=[],
            )

        resolved_request = resolution["resolved_request"]

        # ---------------------------------------------------------
        # 6. Create the initial LangGraph state
        # ---------------------------------------------------------

        initial_state = create_initial_state(
            context,
            conversation_history=conversation_history,
            resolved_request=resolved_request,
        )

        # ---------------------------------------------------------
        # 7. Run the existing MCP + LangGraph workflow
        # ---------------------------------------------------------

        mcp_server = create_mcp_server(context)

        async with Client(mcp_server) as mcp_client:
            graph = build_agent_graph(
                mcp_client=mcp_client,
                execution_context=context,
            )

            graph_result = await graph.ainvoke(
                initial_state,
                config={
                    "configurable": {
                        "thread_id": str(conversation_id),
                    }
                },
            )

        final_result = graph_result.get("final_result")

        if not isinstance(final_result, dict):
            raise RuntimeError(
                "The agent graph did not return a valid final result."
            )

        answer = final_result.get("answer")

        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError(
                "The agent graph returned an invalid answer."
            )

        # ---------------------------------------------------------
        # 8. Save the assistant's response
        # ---------------------------------------------------------

        await save_conversation_message(
            session=session,
            conversation_id=conversation_id,
            user_id=current_user.id,
            request_id=context.request_id,
            role="assistant",
            content=answer,
        )

        await session.commit()

        # ---------------------------------------------------------
        # 9. Return the response to Streamlit
        # ---------------------------------------------------------

        return ChatResponse(
            request_id=context.request_id,
            conversation_id=conversation_id,
            clarification_required=False,
            **final_result,
        )

    except NotFoundError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except HTTPException:
        await session.rollback()
        raise

    except Exception as exc:
        await session.rollback()

        logger.exception(
            "Chat request failed. user_id=%s",
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The chat request could not be completed.",
        ) from exc

# ---------------------------------------------------------------------------
# Audio Transcription - Authenticated users
# ---------------------------------------------------------------------------


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
) -> dict[str, str]:
    """Transcribe an uploaded WAV audio recording."""

    supported_mime_types = {
        "audio/wav",
        "audio/x-wav",
    }

    if audio.content_type not in supported_mime_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported audio format. Please upload a WAV file.",
        )

    try:
        audio_bytes = await audio.read(MAX_AUDIO_BYTES + 1)

        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded audio file is empty.",
            )

        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Audio file exceeds the 10 MB limit.",
            )

        transcript = await transcribe_audio(
            audio_bytes=audio_bytes,
            mime_type=audio.content_type,
        )

        return {"transcript": transcript}

    except HTTPException:
        raise

    except ServerError as exc:
        logger.exception("Gemini transcription service is unavailable.")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The transcription service is temporarily unavailable. "
                "Please try again."
            ),
        ) from exc

    except Exception as exc:
        logger.exception("Audio transcription failed.")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Audio transcription could not be completed.",
        ) from exc

    finally:
        await audio.close()
