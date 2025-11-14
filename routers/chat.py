"""
Chat Router - RAG-based chat endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import json

from databases import get_db
from models import ConversationHistory
from schemas import ChatRequest, ChatResponse
from dependencies.user_profile import enrich_with_user_profile

router = APIRouter(prefix="/chat", tags=["Chat"])


# Dependencies will be injected by main.py
rag_pipeline = None


def set_rag_pipeline(pipeline):
    """Set the RAG pipeline instance"""
    global rag_pipeline
    rag_pipeline = pipeline


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Send a message to the chatbot"""
    try:
        # Enrich layer_config with user profile if user_id is provided
        enriched_layer_config = enrich_with_user_profile(request.user_id, request.layer_config, db)

        response_data = rag_pipeline.chat(
            message=request.message,
            language=request.language,
            session_id=request.session_id,
            user_id=request.user_id,
            source_ids=request.source_ids,
            domain=request.domain,
            min_relevance_score=request.min_relevance_score,
            layer_config=enriched_layer_config,
        )

        # Save conversation to database if user_id is provided
        if request.user_id and response_data.get("response"):
            try:
                conversation = ConversationHistory(
                    user_uuid=request.user_id,
                    session_id=response_data.get("session_id"),
                    user_message=request.message,
                    assistant_message=response_data["response"],
                    domain=request.domain.value if hasattr(request.domain, 'value') else str(request.domain),
                    language=request.language,
                    sources_used=json.dumps([s.dict() for s in response_data.get("sources", [])]),
                    tokens_used=json.dumps(response_data.get("tokens_used", {}))
                )
                db.add(conversation)
                db.commit()
                print(f"[CHAT] Saved conversation to database")
            except Exception as exc:
                db.rollback()
                print(f"[API WARNING] Failed to persist chat history: {exc}")

        # Also use legacy history manager
        if request.user_id and response_data.get("response"):
            try:
                rag_pipeline.record_turn_history(
                    user_id=request.user_id,
                    session_id=response_data.get("session_id"),
                    user_message=request.message,
                    assistant_message=response_data["response"],
                )
            except Exception as exc:
                print(f"[API WARNING] Failed to persist legacy history: {exc}")

        return ChatResponse(**response_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """Send a message to the chatbot with streaming response"""
    print(f"📨 Received streaming chat request: message='{request.message[:50]}...', domain={request.domain}, source_ids={request.source_ids}")
    try:
        # Enrich layer_config with user profile if user_id is provided
        enriched_layer_config = enrich_with_user_profile(request.user_id, request.layer_config, db)

        def generate():
            try:
                accumulated_chunks: List[str] = []
                # Call RAGPipeline directly with streaming
                response_data = rag_pipeline.chat(
                    message=request.message,
                    language=request.language,
                    session_id=request.session_id,
                    user_id=request.user_id,
                    source_ids=request.source_ids,
                    stream=True,
                    domain=request.domain,
                    max_tokens=request.max_tokens,
                    min_relevance_score=request.min_relevance_score,
                    layer_config=enriched_layer_config,
                )
                session_id = response_data.get("session_id")

                # Stream content from OpenAI chunks in SSE format
                for chunk in response_data["stream"]:
                    # Extract content from chunk (similar to how Node.js would parse OpenAI response)
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        accumulated_chunks.append(content)
                        yield f"data: {content}\n\n"

                # Save conversation after streaming completes
                if request.user_id:
                    final_response = "".join(accumulated_chunks).strip()
                    if final_response:
                        try:
                            conversation = ConversationHistory(
                                user_uuid=request.user_id,
                                session_id=session_id,
                                user_message=request.message,
                                assistant_message=final_response,
                                domain=request.domain.value if hasattr(request.domain, 'value') else str(request.domain),
                                language=request.language
                            )
                            db.add(conversation)
                            db.commit()
                            print(f"[CHAT STREAM] Saved conversation to database")
                        except Exception as exc:
                            db.rollback()
                            print(f"[API WARNING] Failed to persist streaming chat history to DB: {exc}")

                        # Also use legacy history manager
                        try:
                            rag_pipeline.record_turn_history(
                                user_id=request.user_id,
                                session_id=session_id,
                                user_message=request.message,
                                assistant_message=final_response,
                            )
                        except Exception as exc:
                            print(f"[API WARNING] Failed to persist legacy history: {exc}")

            except Exception as e:
                import traceback
                error_msg = f"Stream generation error: {str(e)}"
                print(error_msg)
                print(traceback.format_exc())
                # Even errors should be in raw format
                error_data = f"data: {json.dumps({'error': str(e)})}\n\n"
                yield error_data

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        print(f"❌ Chat stream error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
