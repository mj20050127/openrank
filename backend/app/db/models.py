from sqlalchemy import Column, Integer, Text, Date, Float, Boolean, TIMESTAMP, func, JSON
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")

class MetricPoint(Base):
    __tablename__ = "metric_points"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    metric = Column(Text, nullable=False, index=True)
    dt = Column(Date, nullable=False, index=True)
    value = Column(Float)
    source = Column(Text, default="opendigger")
    updated_at = Column(TIMESTAMP, server_default=func.now())

class RepoSnapshot(Base):
    __tablename__ = "repo_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    window_days = Column(Integer, nullable=False)
    snapshot_json = Column(JSONType, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    mode = Column(Text, nullable=False)
    query = Column(Text, nullable=False)
    payload_json = Column(JSONType, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class WatchList(Base):
    __tablename__ = "watchlist"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, unique=True, index=True)
    rules_json = Column(JSONType, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    metric = Column(Text, nullable=False, index=True)
    level = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    evidence_json = Column(JSONType)
    created_at = Column(TIMESTAMP, server_default=func.now())

class RepoCatalog(Base):
    __tablename__ = "repo_catalog"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, unique=True, index=True)
    domain = Column(Text)
    language = Column(Text)
    tags_json = Column(JSONType)
    difficulty = Column(Integer)
    tech_family = Column(Text)
    notes = Column(Text)


class DataEaseBinding(Base):
    __tablename__ = "dataease_bindings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, unique=True, index=True)
    datasource_id = Column(Text)
    dataset_ids = Column(JSONType)
    screen_id = Column(Text)
    embed_url = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
