import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)
VECTOR_DIM = int(os.getenv("PGVECTOR_DIM", "384"))


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


class PatentChunk(Base):
    __tablename__ = "patent_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patent_id: Mapped[str] = mapped_column(ForeignKey("patents.patent_id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index(
    "ix_patent_chunks_patent_id",
    PatentChunk.patent_id,
)

Index(
    "ix_patent_chunks_embedding_ivfflat",
    PatentChunk.embedding,
    postgresql_using="ivfflat",
    postgresql_with={"lists": 100},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)


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
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)


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


def has_patent_chunks(patent_id):
    Session = get_session_maker()
    with Session() as session:
        count = session.query(PatentChunk).filter(PatentChunk.patent_id == patent_id).count()
        return count > 0


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


def replace_patent_chunks(patent_id, chunks, embeddings):
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    Session = get_session_maker()
    with Session() as session:
        now = _now_utc()
        session.query(PatentChunk).filter(PatentChunk.patent_id == patent_id).delete()

        rows = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            rows.append(
                PatentChunk(
                    patent_id=patent_id,
                    chunk_index=idx,
                    chunk_text=chunk,
                    embedding=embedding,
                    created_at=now,
                    updated_at=now,
                )
            )

        if rows:
            session.bulk_save_objects(rows)
        session.commit()


def search_patent_chunks(patent_id, query_embedding, top_k=4):
    Session = get_session_maker()
    with Session() as session:
        rows = (
            session.query(PatentChunk.chunk_text)
            .filter(PatentChunk.patent_id == patent_id)
            .order_by(PatentChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
            .all()
        )
        return [row[0] for row in rows]
