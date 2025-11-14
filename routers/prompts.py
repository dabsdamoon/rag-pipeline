"""
Prompts Router - Prompt management
"""
from fastapi import APIRouter, HTTPException

from schemas import (
    PromptListResponse,
    PromptResponse,
    PromptCreateRequest,
    PromptCreateResponse
)

router = APIRouter(prefix="/prompts", tags=["Prompts"])


# Dependencies will be injected by main.py
prompt_manager = None


def set_prompt_manager(manager):
    """Set the prompt manager instance"""
    global prompt_manager
    prompt_manager = manager


@router.get("/", response_model=PromptListResponse)
def list_prompts():
    """List available prompts"""
    prompts_data = prompt_manager.list_prompts()
    prompts = [PromptResponse(**prompt) for prompt in prompts_data]
    return PromptListResponse(prompts=prompts)


@router.post("/", response_model=PromptCreateResponse)
def create_prompt(request: PromptCreateRequest):
    """Create or update a prompt"""
    prompt_id = request.name.lower().replace(" ", "_")
    prompt_manager.add_prompt(prompt_id, request.template, request.description)

    return PromptCreateResponse(
        prompt_id=prompt_id,
        message="Prompt created successfully"
    )


@router.get("/{prompt_id}", response_model=PromptResponse)
def get_prompt(prompt_id: str):
    """Get specific prompt"""
    template = prompt_manager.get_prompt(prompt_id)
    if not template:
        raise HTTPException(status_code=404, detail="Prompt not found")

    return PromptResponse(
        prompt_id=prompt_id,
        name=prompt_id.replace("_", " ").title(),
        template=template,
        description=f"Prompt {prompt_id}"
    )
