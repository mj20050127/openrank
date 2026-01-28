from __future__ import annotations

from sqlalchemy import Column, Integer, Text, TIMESTAMP, func, JSON
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class RepoCatalog(Base):
    __tablename__ = "repo_catalog"

    repo_full_name = Column(Text, primary_key=True)
    description = Column(Text)
    homepage = Column(Text)
    primary_language = Column(Text)
    domains = Column(JSONType, nullable=False, server_default="[]")
    stacks = Column(JSONType, nullable=False, server_default="[]")
    tags = Column(JSONType, nullable=False, server_default="[]")

    # 兼容旧字段，保留种子领域等信息
    topics = Column(JSONType)
    default_branch = Column(Text)
    license = Column(Text)
    stars = Column(Integer)
    forks = Column(Integer)
    open_issues_count = Column(Integer)
    pushed_at = Column(TIMESTAMP)
    seed_domain = Column(Text)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
