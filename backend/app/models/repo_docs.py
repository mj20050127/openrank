from __future__ import annotations

from sqlalchemy import Column, JSON, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class RepoDoc(Base):
    __tablename__ = "repo_docs"

    repo_full_name = Column(Text, primary_key=True)
    path = Column(Text, server_default="README.md")
    sha = Column(Text)
    content = Column(Text)
    readme_text = Column(Text)
    contributing_text = Column(Text)
    pr_template_text = Column(Text)
    extracted = Column(JSONType, nullable=False, server_default="{}")

    fetched_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # 兼容旧脚本字段
    raw_paths = Column(JSONType)
