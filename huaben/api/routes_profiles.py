"""读者(profile = 人):列表 / 新建 / 改名。不做删除——删人就得处置他的书,用户偏好是不随手删内容。"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import repo
from .deps import get_conn

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


class ProfileName(BaseModel):
    name: str = Field(min_length=1, max_length=20)


def profile_or_404(conn, profile_id: int) -> dict:
    p = repo.get_profile(conn, profile_id)
    if p is None:
        raise HTTPException(404, "这个读者不存在")
    return p


@router.get("")
def list_profiles(conn=Depends(get_conn)):
    return repo.list_profiles(conn)


@router.post("", status_code=201)
def create_profile(body: ProfileName, conn=Depends(get_conn)):
    try:
        pid = repo.create_profile(conn, body.name.strip())
    except sqlite3.IntegrityError as e:
        raise HTTPException(409, f"已经有叫「{body.name.strip()}」的读者了") from e
    return repo.get_profile(conn, pid)


@router.put("/{profile_id}")
def rename_profile(profile_id: int, body: ProfileName, conn=Depends(get_conn)):
    profile_or_404(conn, profile_id)
    try:
        repo.rename_profile(conn, profile_id, body.name.strip())
    except sqlite3.IntegrityError as e:
        raise HTTPException(409, f"已经有叫「{body.name.strip()}」的读者了") from e
    return repo.get_profile(conn, profile_id)
