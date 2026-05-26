"""REST API for aroma session control."""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from smart_aroma.auth_store import (
    AuthRequest,
    AuthResponse,
    HistoryCreate,
    RegisterRequest,
    auth_store,
)
from smart_aroma.models.cabin_context import (
    CabinContext,
    CabinRecommendation,
    CabinSnapshot,
    recommend_from_cabin,
    simulated_cabin_snapshot,
)
from smart_aroma.models.sequence_schema import AromaPlan, StartRequest

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["control"])


class ActionResponse(BaseModel):
    ok: bool
    message: str


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )
    return authorization.removeprefix("Bearer ").strip()


def current_user(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = _bearer_token(authorization)
    user = auth_store.user_for_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效，请重新登录",
        )
    return user


@router.post("/auth/register", response_model=AuthResponse, tags=["auth"])
def register(body: RegisterRequest) -> AuthResponse:
    try:
        result = auth_store.register(body.username, body.password, body.display_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    log.info("REST POST /api/auth/register username=%s", body.username)
    return AuthResponse(**result)


@router.post("/auth/login", response_model=AuthResponse, tags=["auth"])
def login(body: AuthRequest) -> AuthResponse:
    try:
        result = auth_store.login(body.username, body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    log.info("REST POST /api/auth/login username=%s", body.username)
    return AuthResponse(**result)


@router.get("/auth/me", tags=["auth"])
def me(user: dict[str, str] = Depends(current_user)) -> dict[str, str]:
    return user


@router.post("/auth/logout", response_model=ActionResponse, tags=["auth"])
def logout(authorization: str | None = Header(default=None)) -> ActionResponse:
    token = _bearer_token(authorization)
    auth_store.logout(token)
    return ActionResponse(ok=True, message="已退出登录")


@router.get("/history", tags=["history"])
def get_history(user: dict[str, str] = Depends(current_user)) -> list[dict]:
    return auth_store.history_for_user(user["id"])


@router.post("/history", tags=["history"])
def add_history(body: HistoryCreate, user: dict[str, str] = Depends(current_user)) -> dict:
    entry = auth_store.add_history(user["id"], body)
    log.info("REST POST /api/history user=%s scene=%s", user["username"], body.scene)
    return entry


@router.delete("/history/{entry_id}", response_model=ActionResponse, tags=["history"])
def delete_history(entry_id: str, user: dict[str, str] = Depends(current_user)) -> ActionResponse:
    changed = auth_store.delete_history(user["id"], entry_id)
    if not changed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="历史记录不存在")
    return ActionResponse(ok=True, message="已删除历史记录")


@router.post("/history/{entry_id}/start", response_model=ActionResponse, tags=["history"])
def start_from_history(
    entry_id: str,
    request: Request,
    user: dict[str, str] = Depends(current_user),
) -> ActionResponse:
    entry = auth_store.get_history_entry(user["id"], entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="历史记录不存在")
    plan_payload = entry.get("plan")
    if not plan_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="这条历史记录缺少完整方案，请重新生成一次后再复用",
        )
    plan = AromaPlan.model_validate(plan_payload)
    ok, msg = request.app.state.controller.start_plan(plan)
    log.info("REST POST /api/history/%s/start user=%s ok=%s", entry_id, user["username"], ok)
    return ActionResponse(ok=ok, message=msg)


@router.post("/recommend", response_model=CabinRecommendation, tags=["cabin"])
def recommend(body: CabinContext, user: dict[str, str] = Depends(current_user)) -> CabinRecommendation:
    recommendation = recommend_from_cabin(body)
    log.info(
        "REST POST /api/recommend user=%s scene=%s confidence=%s",
        user["username"],
        recommendation.scene,
        recommendation.confidence,
    )
    return recommendation


@router.get("/cabin/snapshot", response_model=CabinSnapshot, tags=["cabin"])
def cabin_snapshot(user: dict[str, str] = Depends(current_user)) -> CabinSnapshot:
    snapshot = simulated_cabin_snapshot()
    log.info(
        "REST GET /api/cabin/snapshot user=%s scenario=%s",
        user["username"],
        snapshot.scenario_id,
    )
    return snapshot


@router.get("/state")
def get_state(request: Request) -> dict:
    """Latest snapshot (same shape as WebSocket payloads)."""
    ctrl = request.app.state.controller
    return ctrl.get_public_state()


@router.post("/start", response_model=ActionResponse)
def start_session(body: StartRequest, request: Request) -> ActionResponse:
    ctrl = request.app.state.controller
    ok, msg = ctrl.start(body.scene, body.persona, body.duration_level)
    log.info(
        "REST POST /api/start scene=%s persona=%s duration_level=%s ok=%s",
        body.scene,
        body.persona,
        body.duration_level,
        ok,
    )
    return ActionResponse(ok=ok, message=msg)


@router.post("/pause", response_model=ActionResponse)
def pause_session(request: Request) -> ActionResponse:
    ok, msg = request.app.state.controller.pause()
    log.info("REST POST /api/pause ok=%s", ok)
    return ActionResponse(ok=ok, message=msg)


@router.post("/resume", response_model=ActionResponse)
def resume_session(request: Request) -> ActionResponse:
    ok, msg = request.app.state.controller.resume()
    log.info("REST POST /api/resume ok=%s", ok)
    return ActionResponse(ok=ok, message=msg)


@router.post("/stop", response_model=ActionResponse)
def stop_session(request: Request) -> ActionResponse:
    ok, msg = request.app.state.controller.stop()
    log.info("REST POST /api/stop ok=%s", ok)
    return ActionResponse(ok=ok, message=msg)
