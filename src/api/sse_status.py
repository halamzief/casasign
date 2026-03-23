"""Server-Sent Events (SSE) for real-time signature status updates.

Production-ready SSE with:
- Heartbeat keep-alive (prevents timeout)
- Last-Event-ID for reconnection
- Graceful error handling
- Docker/nginx compatible
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from src.core.audit.audit_service import AuditService
from src.core.repositories.signature_repository import SignatureRepository
from src.database.session import get_session_factory

router = APIRouter(prefix="/api/sign", tags=["SSE"])


@router.get("/status/{request_id}/stream")
async def stream_signature_status(
    request_id: UUID,
    request: Request,
) -> StreamingResponse:
    """Stream real-time signature status updates via SSE.

    Events emitted:
    - connected: Initial connection established
    - status: Current signature status
    - signer_signed: Individual signer completed
    - all_completed: All signatures done
    - heartbeat: Keep-alive every 15s

    Client reconnection:
    - Supports Last-Event-ID header for resume
    - Auto-reconnect on disconnect

    Docker/Production:
    - Heartbeat prevents timeout
    - X-Accel-Buffering: no (nginx)
    - No proxy buffering needed

    Example client:
    ```javascript
    const eventSource = new EventSource('/api/sign/status/{request_id}/stream');

    eventSource.addEventListener('signer_signed', (e) => {
        const data = JSON.parse(e.data);
        console.log(`${data.signer_name} signed!`);
    });

    eventSource.onerror = () => {
        // Browser auto-reconnects with Last-Event-ID
        console.log('Reconnecting...');
    };
    ```
    """
    logger.info(f"SSE connection requested for request {request_id}")

    async def event_stream() -> AsyncGenerator[str, None]:
        """Generate SSE events with proper formatting."""

        session_factory = get_session_factory()
        session = session_factory()

        # Get Last-Event-ID for reconnection support
        last_event_id = request.headers.get("Last-Event-ID", "0")
        event_counter = int(last_event_id) if last_event_id.isdigit() else 0

        try:
            audit_service = AuditService(session)
            signature_repo = SignatureRepository(session)

            # Send connection established event
            event_counter += 1
            yield format_sse_message(
                event="connected",
                data={
                    "request_id": str(request_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                event_id=event_counter,
            )

            # Get current status
            request_obj = await signature_repo.get_request_by_id(request_id)
            if not request_obj:
                event_counter += 1
                yield format_sse_message(
                    event="error",
                    data={"error": "Request not found"},
                    event_id=event_counter,
                )
                return

            signers = await signature_repo.get_signers_by_request(request_id)

            # Send initial status
            event_counter += 1
            yield format_sse_message(
                event="status",
                data={
                    "request_id": str(request_id),
                    "status": request_obj.status,
                    "signers": [
                        {
                            "id": str(s.id),
                            "name": s.name,
                            "role": s.role,
                            "signed_at": s.signed_at.isoformat() if s.signed_at else None,
                            "is_signed": s.signed_at is not None,
                        }
                        for s in signers
                    ],
                    "progress": {
                        "completed": sum(1 for s in signers if s.signed_at),
                        "total": len(signers),
                    },
                },
                event_id=event_counter,
            )

            # Track last seen event for incremental updates
            last_check = datetime.now(timezone.utc)
            heartbeat_counter = 0

            # Stream updates until request is completed or client disconnects
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from SSE stream: {request_id}")
                    break

                # Check for new audit events
                new_events = await audit_service.get_events_since(
                    request_id=request_id,
                    since=last_check,
                )

                for audit_event in new_events:
                    event_type = audit_event.get("event_type")
                    created_at = audit_event.get("created_at")

                    # Update last_check to this event's timestamp
                    if created_at:
                        last_check = datetime.fromisoformat(created_at)

                    # Map audit events to SSE events
                    if event_type == "signed":
                        # Someone signed!
                        signers = await signature_repo.get_signers_by_request(request_id)

                        event_counter += 1
                        yield format_sse_message(
                            event="signer_signed",
                            data={
                                "signer_name": audit_event.get("metadata", {}).get("signer_name"),
                                "signer_email": audit_event.get("actor_email"),
                                "timestamp": created_at,
                                "progress": {
                                    "completed": sum(1 for s in signers if s.signed_at),
                                    "total": len(signers),
                                },
                            },
                            event_id=event_counter,
                        )

                    elif event_type == "completed":
                        # All signed!
                        event_counter += 1
                        yield format_sse_message(
                            event="all_completed",
                            data={
                                "request_id": str(request_id),
                                "timestamp": created_at,
                            },
                            event_id=event_counter,
                        )
                        logger.info(f"All signatures completed, closing SSE stream: {request_id}")
                        return  # Close stream

                    elif event_type == "link_clicked":
                        event_counter += 1
                        yield format_sse_message(
                            event="link_clicked",
                            data={
                                "signer_email": audit_event.get("actor_email"),
                                "timestamp": created_at,
                            },
                            event_id=event_counter,
                        )

                # Send heartbeat every 15s to prevent timeout
                heartbeat_counter += 1
                if heartbeat_counter >= 5:  # 5 iterations × 3s = 15s
                    event_counter += 1
                    yield format_sse_message(
                        event="heartbeat",
                        data={"timestamp": datetime.now(timezone.utc).isoformat()},
                        event_id=event_counter,
                    )
                    heartbeat_counter = 0

                # Wait 3 seconds before next check (lightweight polling on backend)
                await asyncio.sleep(3)

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled: {request_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}", exc_info=True)
            event_counter += 1
            yield format_sse_message(
                event="error",
                data={"error": str(e)},
                event_id=event_counter,
            )
        finally:
            await session.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


def format_sse_message(event: str, data: dict, event_id: int) -> str:
    """Format SSE message according to specification.

    SSE format:
    id: {event_id}
    event: {event_type}
    data: {json_data}

    (blank line to end message)
    """
    return f"id: {event_id}\nevent: {event}\ndata: {json.dumps(data)}\n\n"
