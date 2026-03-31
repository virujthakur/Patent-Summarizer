import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import JSON, DateTime, LargeBinary, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)


class Base(DeclarativeBase):
    pass


class PatentRecord(Base):
    __tablename__ = "patents"

    patent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embeddings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _now_utc():
    return datetime.now(timezone.utc)


def _get_database_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Configure a PostgreSQL URL, for example: "
            "postgresql+psycopg2://user:password@localhost:5432/patent_studio"
        )
    return url


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(_get_database_url(), pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def get_session_maker():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(bind=get_engine())


def _to_payload(record: PatentRecord | None):
    if record is None:
        return None

    return {
        "patent_id": record.patent_id,
        "url": record.url,
        "pdf_data": record.pdf_data,
        "text_content": record.text_content,
        "summary": record.summary,
        "chunks": record.chunks,
        "embeddings": record.embeddings,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def get_patent_record(patent_id):
    Session = get_session_maker()
    with Session() as session:
        record = session.get(PatentRecord, patent_id)
        return _to_payload(record)


def upsert_patent_record(
    patent_id,
    url,
    pdf_data=None,
    text_content=None,
    summary=None,
    chunks=None,
    embeddings=None,
):
    Session = get_session_maker()
    with Session() as session:
        record = session.get(PatentRecord, patent_id)
        now = _now_utc()

        if record is None:
            record = PatentRecord(
                patent_id=patent_id,
                url=url,
                created_at=now,
                updated_at=now,
            )

        record.url = url
        record.updated_at = now
        if pdf_data is not None:
            record.pdf_data = pdf_data
        if text_content is not None:
            record.text_content = text_content
        if summary is not None:
            record.summary = summary
        if chunks is not None:
            record.chunks = chunks
        if embeddings is not None:
            record.embeddings = embeddings

        session.add(record)
        session.commit()
        session.refresh(record)
        return _to_payload(record)
