from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from shutil import rmtree
from uuid import UUID, uuid4

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field


logger = logging.getLogger(__name__)
ATTACHMENT_CHUNK_SIZE = 1024 * 1024
MAX_ATTACHMENTS_PER_THREAD = 10

ATTACHMENT_SIZE_LIMITS = {
    "image": 10 * 1024 * 1024,
    "pdf": 25 * 1024 * 1024,
    "text-file": 10 * 1024 * 1024,
}


@dataclass(frozen=True)
class ThreadStoredAttachment:
    attachment_id: str
    thread_id: str
    kind: str
    name: str
    mime_type: str
    size: int
    path: Path
    created_at: datetime


class StoredAttachmentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    attachment_id: str = Field(alias="attachmentId")
    thread_id: str = Field(alias="threadId")
    kind: str
    name: str
    mime_type: str = Field(alias="mimeType")
    size: int = Field(ge=0)
    created_at: datetime = Field(alias="createdAt")


class ThreadAttachmentError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def classify_attachment(content_type: str, file_name: str) -> str | None:
    lower_name = file_name.lower()
    if content_type.startswith("image/"):
        return "image"
    if content_type == "application/pdf" or lower_name.endswith(".pdf"):
        return "pdf"
    if (
        content_type.startswith("text/")
        or content_type == "application/json"
        or lower_name.endswith((".txt", ".md", ".markdown", ".csv", ".json"))
    ):
        return "text-file"
    return None


class ThreadAttachmentService:
    def __init__(self, *, storage_root: Path) -> None:
        self.storage_root = storage_root

    async def save_upload(
        self,
        *,
        thread_id: str,
        upload: UploadFile,
    ) -> ThreadStoredAttachment:
        name = Path(upload.filename or "attachment").name or "attachment"
        mime_type = upload.content_type or "application/octet-stream"
        kind = classify_attachment(mime_type, name)
        logger.info(
            "Saving thread attachment upload",
            extra={
                "thread_id": thread_id,
                "file_name": name,
                "mime_type": mime_type,
                "kind": kind,
            },
        )
        if kind is None:
            logger.warning(
                "Thread attachment upload rejected due to unsupported type",
                extra={
                    "thread_id": thread_id,
                    "file_name": name,
                    "mime_type": mime_type,
                },
            )
            raise ThreadAttachmentError("unsupported-type")
        if self._attachment_count(thread_id) >= MAX_ATTACHMENTS_PER_THREAD:
            logger.warning(
                "Thread attachment upload rejected due to attachment limit",
                extra={
                    "thread_id": thread_id,
                    "file_name": name,
                    "max_attachments": MAX_ATTACHMENTS_PER_THREAD,
                },
            )
            raise ThreadAttachmentError("too-many-attachments")

        attachment_id = str(uuid4())
        thread_dir = self._thread_dir(thread_id)
        attachment_dir = thread_dir / attachment_id
        uploading_content = attachment_dir / "content.uploading"
        uploading_metadata = attachment_dir / "metadata.uploading"
        content_path = attachment_dir / "content"
        metadata_path = attachment_dir / "metadata.json"
        max_bytes = ATTACHMENT_SIZE_LIMITS[kind]
        size = 0

        try:
            attachment_dir.mkdir(parents=True, exist_ok=False)
            with uploading_content.open("wb") as target:
                while chunk := await upload.read(ATTACHMENT_CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        logger.warning(
                            "Thread attachment upload rejected due to size limit",
                            extra={
                                "thread_id": thread_id,
                                "file_name": name,
                                "kind": kind,
                                "size": size,
                                "max_bytes": max_bytes,
                            },
                        )
                        raise ThreadAttachmentError("too-large")
                    target.write(chunk)

            metadata = StoredAttachmentMetadata(
                attachmentId=attachment_id,
                threadId=thread_id,
                kind=kind,
                name=name,
                mimeType=mime_type,
                size=size,
                createdAt=datetime.now(UTC),
            )
            uploading_metadata.write_text(
                metadata.model_dump_json(by_alias=True),
                encoding="utf-8",
            )
            uploading_content.replace(content_path)
            uploading_metadata.replace(metadata_path)
            logger.info(
                "Thread attachment upload stored",
                extra={
                    "thread_id": thread_id,
                    "attachment_id": attachment_id,
                    "file_name": name,
                    "mime_type": mime_type,
                    "kind": kind,
                    "size": size,
                },
            )
            return ThreadStoredAttachment(
                attachment_id=attachment_id,
                thread_id=thread_id,
                kind=kind,
                name=name,
                mime_type=mime_type,
                size=size,
                path=content_path,
                created_at=metadata.created_at,
            )
        except Exception as exc:
            logger.exception(
                "Thread attachment upload storage failed",
                extra={
                    "thread_id": thread_id,
                    "attachment_id": attachment_id,
                    "file_name": name,
                    "mime_type": mime_type,
                    "kind": kind,
                    "size": size,
                    "error_type": type(exc).__name__,
                },
            )
            rmtree(attachment_dir, ignore_errors=True)
            raise
        finally:
            await upload.close()

    def get_attachment(
        self, thread_id: str, attachment_id: str
    ) -> ThreadStoredAttachment:
        try:
            normalized_id = str(UUID(attachment_id))
        except ValueError as exc:
            raise ThreadAttachmentError("attachment-not-found") from exc
        if normalized_id != attachment_id:
            raise ThreadAttachmentError("attachment-not-found")

        thread_dir = self._thread_dir(thread_id)
        attachment_dir = thread_dir / attachment_id
        metadata_path = attachment_dir / "metadata.json"
        content_path = attachment_dir / "content"
        try:
            resolved_dir = attachment_dir.resolve(strict=False)
            resolved_thread_dir = thread_dir.resolve(strict=False)
            resolved_content = content_path.resolve(strict=True)
            if not resolved_dir.is_relative_to(resolved_thread_dir):
                raise ThreadAttachmentError("attachment-not-found")
            if not resolved_content.is_relative_to(resolved_dir):
                raise ThreadAttachmentError("attachment-not-found")
            if content_path.is_symlink():
                raise ThreadAttachmentError("attachment-not-found")
            metadata = StoredAttachmentMetadata.model_validate(
                json.loads(metadata_path.read_text(encoding="utf-8")),
            )
        except ThreadAttachmentError:
            raise
        except Exception as exc:
            raise ThreadAttachmentError("attachment-not-found") from exc

        if metadata.thread_id != thread_id or metadata.attachment_id != attachment_id:
            raise ThreadAttachmentError("attachment-not-found")
        if metadata.kind not in ATTACHMENT_SIZE_LIMITS:
            raise ThreadAttachmentError("attachment-not-found")
        if resolved_content.stat().st_size != metadata.size:
            raise ThreadAttachmentError("attachment-not-found")

        return ThreadStoredAttachment(
            attachment_id=metadata.attachment_id,
            thread_id=metadata.thread_id,
            kind=metadata.kind,
            name=metadata.name,
            mime_type=metadata.mime_type,
            size=metadata.size,
            path=resolved_content,
            created_at=metadata.created_at,
        )

    def delete_attachment(self, thread_id: str, attachment_id: str) -> None:
        attachment = self.get_attachment(thread_id, attachment_id)
        rmtree(attachment.path.parent)

    def list_attachments(self, thread_id: str) -> list[ThreadStoredAttachment]:
        thread_dir = self._thread_dir(thread_id)
        if not thread_dir.exists():
            return []
        attachments: list[ThreadStoredAttachment] = []
        for path in thread_dir.iterdir():
            if not path.is_dir():
                continue
            try:
                attachments.append(self.get_attachment(thread_id, path.name))
            except ThreadAttachmentError:
                continue
        return sorted(attachments, key=lambda item: item.created_at)

    def _attachment_count(self, thread_id: str) -> int:
        thread_dir = self._thread_dir(thread_id)
        if not thread_dir.exists():
            return 0
        return sum(
            1 for path in thread_dir.iterdir() if (path / "metadata.json").is_file()
        )

    def _thread_dir(self, thread_id: str) -> Path:
        return self.storage_root / thread_id


__all__ = [
    "MAX_ATTACHMENTS_PER_THREAD",
    "ThreadAttachmentError",
    "ThreadAttachmentService",
    "ThreadStoredAttachment",
]
