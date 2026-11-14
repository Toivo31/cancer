"""Who am I and what may I do here (spec 07, tickets M7-2 and M7-6). Public: the web app calls it before it has a token."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from .. import security

router = APIRouter(tags=["access"])


class DataNotice(BaseModel):
    synthetic_only: bool
    text: str


class AccessInfo(BaseModel):
    mode: str                      # open | token | public_read | read_only
    token_required: bool           # true when writing needs the access token
    authenticated: bool            # the token sent with this request is valid (or the instance is open)
    can_write: bool
    data_notice: DataNotice        # show this on the upload page and in the footer
    jev_default_url: str | None = None   # only for callers who may write


@router.get("/access", response_model=AccessInfo)
def access(request: Request):
    cfg = security.config()
    st = getattr(request.state, "pathway_access", None) or {"authenticated": False, "can_write": False}
    return AccessInfo(mode=cfg.mode, token_required=not cfg.open_mode, authenticated=st["authenticated"], can_write=st["can_write"],
                      data_notice=DataNotice(synthetic_only=cfg.synthetic_only, text=cfg.notice if cfg.synthetic_only else ""),
                      jev_default_url=cfg.jev_default_url if st["can_write"] else None)
