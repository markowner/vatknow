from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Space, SpaceMember, User
from app.schemas.common import MemberCreate, MemberOut, MemberUpdate, SpaceCreate, SpaceOut, SpaceUpdate
from app.services.access import owner_count, require_role
from app.services.slugs import slugify, unique_space_slug

router = APIRouter(prefix="/spaces", tags=["spaces"])


def _space_out(space: Space, role: str) -> SpaceOut:
    return SpaceOut(
        id=space.id,
        name=space.name,
        kind=space.kind,
        role=role,
        visibility=space.visibility or "private",
        slug=space.slug,
        created_at=space.created_at,
    )


@router.get("", response_model=list[SpaceOut])
def list_spaces(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SpaceOut]:
    rows = db.execute(
        select(Space, SpaceMember.role)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .where(SpaceMember.user_id == user.id)
        .order_by(Space.created_at.asc())
    ).all()
    return [_space_out(space, role) for space, role in rows]


@router.post("", response_model=SpaceOut, status_code=status.HTTP_201_CREATED)
def create_space(
    body: SpaceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SpaceOut:
    slug = unique_space_slug(db, slugify(body.slug, body.name)) if body.visibility == "public" or body.slug else None
    space = Space(
        name=body.name.strip(),
        kind="team",
        visibility=body.visibility,
        slug=slug,
        created_by=user.id,
    )
    db.add(space)
    db.flush()
    db.add(SpaceMember(space_id=space.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(space)
    return _space_out(space, "owner")


@router.get("/{space_id}", response_model=SpaceOut)
def get_space(
    space_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SpaceOut:
    space, member = require_role(db, user, space_id, "viewer")
    return _space_out(space, member.role)


@router.patch("/{space_id}", response_model=SpaceOut)
def update_space(
    space_id: UUID,
    body: SpaceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpaceOut:
    space, member = require_role(db, user, space_id, "admin")
    if body.name is not None:
        space.name = body.name.strip()
    if body.visibility is not None:
        space.visibility = body.visibility
    if body.slug is not None:
        space.slug = unique_space_slug(db, slugify(body.slug, space.name), exclude_id=space.id) if body.slug.strip() else None
    if space.visibility == "public" and not space.slug:
        space.slug = unique_space_slug(db, slugify(space.name), exclude_id=space.id)
    if space.visibility == "private":
        space.slug = space.slug
    db.commit()
    db.refresh(space)
    return _space_out(space, member.role)


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_space(
    space_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    space, _member = require_role(db, user, space_id, "owner")
    if space.kind == "personal":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="个人空间不能删除")
    db.delete(space)
    db.commit()


@router.get("/{space_id}/members", response_model=list[MemberOut])
def list_members(
    space_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[MemberOut]:
    require_role(db, user, space_id, "viewer")
    rows = db.execute(
        select(SpaceMember, User)
        .join(User, User.id == SpaceMember.user_id)
        .where(SpaceMember.space_id == space_id)
    ).all()
    return [
        MemberOut(user_id=member.user_id, email=member_user.email, name=member_user.name, role=member.role)
        for member, member_user in rows
    ]


@router.post("/{space_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    space_id: UUID,
    body: MemberCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberOut:
    space, _member = require_role(db, user, space_id, "admin")
    if space.kind == "personal":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="个人空间不能邀请成员")
    target = db.scalar(select(User).where(User.email == body.email.lower()))
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该邮箱尚未注册")
    existing = db.scalar(
        select(SpaceMember).where(SpaceMember.space_id == space_id, SpaceMember.user_id == target.id)
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该用户已在空间中")
    member = SpaceMember(space_id=space_id, user_id=target.id, role=body.role)
    db.add(member)
    db.commit()
    return MemberOut(user_id=target.id, email=target.email, name=target.name, role=body.role)


@router.patch("/{space_id}/members/{user_id}", response_model=MemberOut)
def update_member(
    space_id: UUID,
    user_id: UUID,
    body: MemberUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberOut:
    space, _member = require_role(db, user, space_id, "admin")
    if space.kind == "personal":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="个人空间不能修改成员")
    target_member = db.scalar(
        select(SpaceMember).where(SpaceMember.space_id == space_id, SpaceMember.user_id == user_id)
    )
    if target_member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    if target_member.role == "owner" and body.role != "owner" and owner_count(db, space_id) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能取消最后一位所有者")
    if body.role == "owner":
        require_role(db, user, space_id, "owner")
    target_member.role = body.role
    db.commit()
    target = db.get(User, user_id)
    assert target is not None
    return MemberOut(user_id=target.id, email=target.email, name=target.name, role=target_member.role)


@router.delete("/{space_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    space_id: UUID,
    user_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    space, _member = require_role(db, user, space_id, "admin")
    if space.kind == "personal":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="个人空间不能移除成员")
    target_member = db.scalar(
        select(SpaceMember).where(SpaceMember.space_id == space_id, SpaceMember.user_id == user_id)
    )
    if target_member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    if target_member.role == "owner" and owner_count(db, space_id) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能移除最后一位所有者")
    db.delete(target_member)
    db.commit()
