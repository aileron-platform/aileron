from __future__ import annotations

from tempfile import SpooledTemporaryFile

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.modules.thread.attachments import (
    MAX_ATTACHMENTS_PER_THREAD,
    ThreadAttachmentError,
    ThreadAttachmentService,
)


def make_upload_file(name: str, content_type: str, content: bytes) -> UploadFile:
    file = SpooledTemporaryFile()
    file.write(content)
    file.seek(0)
    return UploadFile(
        file=file,
        filename=name,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_save_upload_rejects_unsupported_type(tmp_path) -> None:
    service = ThreadAttachmentService(storage_root=tmp_path)

    with pytest.raises(ThreadAttachmentError) as exc:
        await service.save_upload(
            thread_id="thread-1",
            upload=make_upload_file("archive.zip", "application/zip", b"zip"),
        )

    assert exc.value.code == "unsupported-type"


@pytest.mark.asyncio
async def test_save_upload_rejects_oversized_pdf(tmp_path) -> None:
    service = ThreadAttachmentService(storage_root=tmp_path)

    with pytest.raises(ThreadAttachmentError) as exc:
        await service.save_upload(
            thread_id="thread-1",
            upload=make_upload_file(
                "large.pdf",
                "application/pdf",
                b"x" * (25 * 1024 * 1024 + 1),
            ),
        )

    assert exc.value.code == "too-large"


@pytest.mark.asyncio
async def test_save_upload_persists_supported_pdf(tmp_path) -> None:
    service = ThreadAttachmentService(storage_root=tmp_path)

    attachment = await service.save_upload(
        thread_id="thread-1",
        upload=make_upload_file("spec.pdf", "application/pdf", b"%PDF"),
    )

    assert attachment.kind == "pdf"
    assert attachment.name == "spec.pdf"
    assert attachment.mime_type == "application/pdf"
    assert attachment.size == 4
    assert attachment.path.read_bytes() == b"%PDF"


@pytest.mark.asyncio
async def test_attachment_survives_service_restart(tmp_path) -> None:
    first = ThreadAttachmentService(storage_root=tmp_path)
    stored = await first.save_upload(
        thread_id="thread-1",
        upload=make_upload_file("notes.md", "text/markdown", b"# notes"),
    )

    second = ThreadAttachmentService(storage_root=tmp_path)
    resolved = second.get_attachment("thread-1", stored.attachment_id)

    assert resolved.name == "notes.md"
    assert resolved.path.read_bytes() == b"# notes"


@pytest.mark.asyncio
async def test_cross_thread_reference_is_not_resolved(tmp_path) -> None:
    service = ThreadAttachmentService(storage_root=tmp_path)
    stored = await service.save_upload(
        thread_id="thread-1",
        upload=make_upload_file("notes.md", "text/markdown", b"notes"),
    )

    with pytest.raises(ThreadAttachmentError) as exc:
        service.get_attachment("thread-2", stored.attachment_id)

    assert exc.value.code == "attachment-not-found"


@pytest.mark.asyncio
async def test_oversized_upload_removes_partial_files(tmp_path) -> None:
    service = ThreadAttachmentService(storage_root=tmp_path)

    with pytest.raises(ThreadAttachmentError):
        await service.save_upload(
            thread_id="thread-1",
            upload=make_upload_file(
                "large.pdf",
                "application/pdf",
                b"x" * (25 * 1024 * 1024 + 1),
            ),
        )

    assert list(tmp_path.rglob("*.uploading")) == []
    assert list(tmp_path.rglob("content")) == []


@pytest.mark.asyncio
async def test_save_upload_rejects_more_than_ten_attachments(tmp_path) -> None:
    service = ThreadAttachmentService(storage_root=tmp_path)

    for index in range(MAX_ATTACHMENTS_PER_THREAD):
        await service.save_upload(
            thread_id="thread-1",
            upload=make_upload_file(
                f"notes-{index}.md",
                "text/markdown",
                b"notes",
            ),
        )

    with pytest.raises(ThreadAttachmentError) as exc:
        await service.save_upload(
            thread_id="thread-1",
            upload=make_upload_file("overflow.md", "text/markdown", b"overflow"),
        )

    assert exc.value.code == "too-many-attachments"


@pytest.mark.asyncio
async def test_get_attachment_rejects_symlinked_content(tmp_path) -> None:
    service = ThreadAttachmentService(storage_root=tmp_path)
    stored = await service.save_upload(
        thread_id="thread-1",
        upload=make_upload_file("notes.md", "text/markdown", b"notes"),
    )
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    stored.path.unlink()
    stored.path.symlink_to(outside)

    with pytest.raises(ThreadAttachmentError) as exc:
        service.get_attachment("thread-1", stored.attachment_id)

    assert exc.value.code == "attachment-not-found"


@pytest.mark.asyncio
async def test_get_attachment_rejects_malformed_attachment_id(tmp_path) -> None:
    service = ThreadAttachmentService(storage_root=tmp_path)

    with pytest.raises(ThreadAttachmentError) as exc:
        service.get_attachment("thread-1", "../../etc/passwd")

    assert exc.value.code == "attachment-not-found"
