from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Integer,
    JSON,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import synonym

from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class RepoIssue(Base):
    __tablename__ = "repo_issues"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    repo_full_name = Column(Text, nullable=False)
    issue_number = Column(Integer, nullable=False)
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    labels = Column(JSONType, nullable=False, server_default="[]")
    updated_at = Column(TIMESTAMP, nullable=False)
    category = Column(Text, nullable=False)  # good_first/help_wanted/docs/i18n
    difficulty = Column(Text)

    fetched_at = Column(TIMESTAMP, server_default=func.now())

    # 兼容旧脚本字段
    body = Column(Text)
    state = Column(Text)
    is_pull_request = Column(Boolean, default=False)
    author_login = Column(Text)
    author_association = Column(Text)
    comments = Column(Integer)
    created_at = Column(TIMESTAMP)
    github_issue_id = Column(BigInteger)
    raw = Column(JSONType)

    number = synonym("issue_number")

    __table_args__ = (
        UniqueConstraint("repo_full_name", "issue_number", name="uq_repo_issue"),
        Index("idx_repo_issues_repo_cat", repo_full_name, category),
        Index("idx_repo_issues_updated", updated_at.desc()),
        Index("idx_repo_issues_labels_gin", labels, postgresql_using="gin"),
    )
