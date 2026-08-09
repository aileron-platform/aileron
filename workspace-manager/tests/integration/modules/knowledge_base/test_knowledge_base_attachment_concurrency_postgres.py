"""Real PostgreSQL concurrency tests for knowledge base attachments."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import Base
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import AuthorizationOperationError
from app.modules.knowledge_base.access import (
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
)
from app.modules.knowledge_base.attachments import KnowledgeBaseAttachmentService

_OWNER_ID = "knowledge-base-race-owner"
_OWNER_ACTOR = AuthorizationActor(user_id=_OWNER_ID, platform_role="member")
_WORKSPACE_ID = "55555555-5555-4555-8555-555555555555"
_PRIMARY_KB_ID = "66666666-6666-4666-8666-666666666666"
_SECONDARY_KB_ID = "77777777-7777-4777-8777-777777777777"
_AttachmentServiceType = type[KnowledgeBaseAttachmentService]


@pytest.fixture()
def knowledge_base_attachment_database() -> Engine:
    database_url = os.environ.get("AUTOMATION_TEST_DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.fail("A real PostgreSQL integration database is required")

    schema = f"knowledge_base_attachment_{uuid4().hex}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def _seed_workspace_and_knowledge_bases(
    engine: Engine, *, include_second: bool
) -> None:
    knowledge_bases = [
        db_models.KnowledgeBase(
            id=_PRIMARY_KB_ID,
            slug="primary-docs",
            name="Primary docs",
            owner_id=_OWNER_ID,
            current_size_bytes=0,
        )
    ]
    if include_second:
        knowledge_bases.append(
            db_models.KnowledgeBase(
                id=_SECONDARY_KB_ID,
                slug="secondary-docs",
                name="Secondary docs",
                owner_id=_OWNER_ID,
                current_size_bytes=0,
            )
        )

    with Session(engine) as session:
        session.add(
            db_models.User(
                id=_OWNER_ID,
                username="knowledge-base-race-owner",
                email="knowledge-base-race-owner@example.com",
                is_active=True,
                identity_enabled=True,
                sync_status="synced",
                platform_role="member",
                role_status="valid",
            )
        )
        session.add(
            db_models.Workspace(
                id=_WORKSPACE_ID,
                owner_id=_OWNER_ID,
                name="Attachment race workspace",
                runtime="universal",
                provisioner="docker",
                runtime_status="stopped",
            )
        )
        session.add_all(knowledge_bases)
        session.commit()


def _attach(
    engine: Engine,
    *,
    kb_id: str,
    mount_alias: str,
    service_type: _AttachmentServiceType = KnowledgeBaseAttachmentService,
) -> tuple[str, str]:
    with Session(engine) as session:
        try:
            result = service_type(session).attach(
                actor=_OWNER_ACTOR,
                workspace_id=_WORKSPACE_ID,
                kb_id=kb_id,
                mount_alias=mount_alias,
                correlation_id=str(uuid4()),
            )
            return "attached", result.attachment.id
        except (
            AuthorizationOperationError,
            KnowledgeBaseConflictError,
            KnowledgeBaseNotFoundError,
        ) as exc:
            code = (
                exc.error_code
                if isinstance(exc, AuthorizationOperationError)
                else exc.code
            )
            return "rejected", code


def _delete(
    engine: Engine,
    *,
    service_type: type[KnowledgeBaseService] = KnowledgeBaseService,
) -> tuple[str, str]:
    with Session(engine) as session:
        try:
            service_type(session).delete_kb(
                actor=_OWNER_ACTOR,
                kb_id=_PRIMARY_KB_ID,
                confirmation_name="Primary docs",
            )
            return "deleted", _PRIMARY_KB_ID
        except KnowledgeBaseConflictError as exc:
            return "rejected", exc.code


def test_concurrent_same_alias_has_one_winner_and_stable_conflict(
    knowledge_base_attachment_database: Engine,
) -> None:
    engine = knowledge_base_attachment_database
    _seed_workspace_and_knowledge_bases(engine, include_second=True)
    ready = Barrier(2)

    def attach_after_barrier(kb_id: str) -> tuple[str, str]:
        ready.wait(timeout=10)
        return _attach(engine, kb_id=kb_id, mount_alias="shared-docs")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attach_after_barrier, kb_id)
            for kb_id in (_PRIMARY_KB_ID, _SECONDARY_KB_ID)
        ]
        outcomes = [future.result(timeout=20) for future in futures]

    assert sorted(outcome[0] for outcome in outcomes) == ["attached", "rejected"]
    assert next(detail for status, detail in outcomes if status == "rejected") == (
        "KB_MOUNT_ALIAS_CONFLICT"
    )


@pytest.mark.parametrize("first_committer", ("attach", "delete"))
def test_attach_and_permanent_delete_race_preserves_reference_fencing(
    knowledge_base_attachment_database: Engine,
    first_committer: str,
) -> None:
    engine = knowledge_base_attachment_database
    _seed_workspace_and_knowledge_bases(engine, include_second=False)
    row_locked = Event()
    release_first = Event()

    class HoldingAttachmentService(KnowledgeBaseAttachmentService):
        def _lock_knowledge_base(self, kb_id: str) -> db_models.KnowledgeBase:
            kb = super()._lock_knowledge_base(kb_id)
            row_locked.set()
            assert release_first.wait(timeout=10)
            return kb

    class HoldingDeleteService(KnowledgeBaseService):
        def delete_kb(
            self,
            *,
            actor: AuthorizationActor,
            kb_id: str,
            confirmation_name: str,
        ) -> db_models.KnowledgeBase:
            knowledge_base = self.db.scalar(
                select(db_models.KnowledgeBase)
                .where(db_models.KnowledgeBase.id == kb_id)
                .with_for_update()
            )
            assert knowledge_base is not None
            row_locked.set()
            assert release_first.wait(timeout=10)
            return super().delete_kb(
                actor=actor,
                kb_id=kb_id,
                confirmation_name=confirmation_name,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        if first_committer == "attach":
            first_future = executor.submit(
                _attach,
                engine,
                kb_id=_PRIMARY_KB_ID,
                mount_alias="docs",
                service_type=HoldingAttachmentService,
            )
            assert row_locked.wait(timeout=10)
            second_future = executor.submit(_delete, engine)
        else:
            first_future = executor.submit(
                _delete,
                engine,
                service_type=HoldingDeleteService,
            )
            assert row_locked.wait(timeout=10)
            second_future = executor.submit(
                _attach,
                engine,
                kb_id=_PRIMARY_KB_ID,
                mount_alias="docs",
            )

        release_first.set()
        first_outcome = first_future.result(timeout=20)
        second_outcome = second_future.result(timeout=20)

    with Session(engine) as session:
        knowledge_base = session.get(db_models.KnowledgeBase, _PRIMARY_KB_ID)
        attachments = list(
            session.scalars(
                select(db_models.WorkspaceKnowledgeBaseAttachment).where(
                    db_models.WorkspaceKnowledgeBaseAttachment.kb_id == _PRIMARY_KB_ID
                )
            ).all()
        )
        if first_committer == "attach":
            assert first_outcome[0] == "attached"
            assert second_outcome == ("rejected", "KB_DELETE_ATTACHMENT_CONFLICT")
            assert knowledge_base is not None
        else:
            assert first_outcome == ("deleted", _PRIMARY_KB_ID)
            assert second_outcome[0] == "rejected"
            assert second_outcome[1] in {"KB_ACCESS_DENIED", "KB_NOT_FOUND"}
            assert knowledge_base is None
        assert attachments == []
