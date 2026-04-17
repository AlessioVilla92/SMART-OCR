"""
Scoring router — recompute CBCL scores from edited items.
"""

from fastapi import APIRouter, Depends

from smart_ocr_backend.db.models import User
from smart_ocr_backend.api.deps import get_current_user
from smart_ocr_backend.schemas.scoring import RecomputeRequest, RecomputeResponse

router = APIRouter(prefix="/score", tags=["scoring"])


@router.post("/recompute", response_model=RecomputeResponse)
def recompute(
    body: RecomputeRequest,
    user: User = Depends(get_current_user),
):
    """
    Recompute CBCL scores from edited item values.
    No ML involved — pure arithmetic. Completes in <500ms.
    """
    from smart_ocr_backend.services.scoring_service import recompute_scores

    result = recompute_scores(
        items=body.items,
        age=body.age,
        gender=body.gender,
        compilatore_str=body.compilatore,
    )
    return RecomputeResponse(**result)
