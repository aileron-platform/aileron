from __future__ import annotations

import json
from pathlib import Path

import pytest

from _common import (
    SkillError,
    build_publication_id,
    copy_content_tree,
    load_publishing_config,
    redact_text,
    result_envelope,
)
from deploy import chart_version, desired_application
from build_site import main as build_site_main
from config import load_site_config, resolve_site_config, write_site_config
from ensure_user_resources import _verify_kit_checksums, _verify_kit_release
from package import chart_version as package_chart_version
from publish import load_canvas_manifest, site_publishing_manifest
from publish import _reusable_pipeline
import rollback as rollback_module
import status as status_module
import unpublish as unpublish_module


def _environment() -> dict[str, str]:
    return {
        "AILERON_PUBLISH_BUILD_PROVIDER": "gitlab",
        "AILERON_PUBLISH_DEPLOY_PROVIDER": "argocd",
        "AILERON_PUBLISH_WORKSPACE_ID": "workspace-123",
        "AILERON_PUBLISH_GITLAB_API": "https://gitlab.example/api/v4",
        "AILERON_PUBLISH_GITLAB_PROJECT_PATH": "platform/canvas-publishing",
        "AILERON_PUBLISH_GITLAB_TOKEN": "gitlab-secret",
        "AILERON_PUBLISH_ARGOCD_URL": "https://argocd.example",
        "AILERON_PUBLISH_ARGOCD_TOKEN": "argocd-secret",
        "AILERON_PUBLISH_ARGOCD_PROJECT": "canvas-sites",
        "AILERON_PUBLISH_OCI_REGISTRY": "registry.example",
        "AILERON_PUBLISH_OCI_SITE_REPOSITORY": "canvas/sites",
        "AILERON_PUBLISH_OCI_CHART_REPOSITORY": "canvas/charts",
        "AILERON_PUBLISH_OCI_PUSH_USERNAME": "robot",
        "AILERON_PUBLISH_OCI_PUSH_PASSWORD": "registry-secret",
        "AILERON_PUBLISH_BASE_DOMAIN": "canvas.example",
        "AILERON_PUBLISH_DESTINATION_NAMESPACE": "workspace-123",
        "AILERON_PUBLISH_RUNTIME_BASE": (
            "registry.example/base/runtime@sha256:" + "a" * 64
        ),
        "AILERON_PUBLISH_NEXTJS_BUILDER": (
            "registry.example/base/builder@sha256:" + "b" * 64
        ),
        "AILERON_PUBLISH_IMAGE_PULL_SECRET_NAME": "canvas-pull",
        "AILERON_PUBLISH_TLS_SECRET_NAME": "canvas-tls",
        "AILERON_PUBLISH_INGRESS_CLASS_NAME": "nginx",
        "AILERON_PUBLISH_RELEASE_VERSION": "2026.08.04",
    }


def test_config_reads_only_workspace_environment(monkeypatch) -> None:
    for key, value in _environment().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("CANVAS_PUBLISH_GITLAB_TOKEN", "legacy-secret")

    config = load_publishing_config()

    assert config.workspace_id == "workspace-123"
    assert config.gitlab_project_path == "platform/canvas-publishing"
    assert config.build_provider == "gitlab"
    assert config.deploy_provider == "argocd"
    assert config.gitlab_token == "gitlab-secret"


def test_config_rejects_missing_or_unknown_provider(monkeypatch) -> None:
    for key, value in _environment().items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AILERON_PUBLISH_GITLAB_TOKEN")

    with pytest.raises(SkillError) as error:
        load_publishing_config()

    assert error.value.error_code == "PUBLISHING_CONFIG_MISSING"
    assert "gitlab_token" in error.value.details["missing"]

    monkeypatch.setenv("AILERON_PUBLISH_GITLAB_TOKEN", "gitlab-secret")
    monkeypatch.setenv("AILERON_PUBLISH_BUILD_PROVIDER", "github")

    with pytest.raises(SkillError) as error:
        load_publishing_config()

    assert error.value.error_code == "PUBLISHING_PROVIDER_UNSUPPORTED"


def test_result_envelope_contains_provider_neutral_fields() -> None:
    payload = result_envelope(
        operation="status",
        status="READY",
        phase="VERIFYING",
        site_id="site-123",
        publication_id="pub-abc",
        evidence={"git": {"commit": "a" * 40}},
    )

    assert payload == {
        "schemaVersion": 1,
        "operation": "status",
        "status": "READY",
        "phase": "VERIFYING",
        "siteId": "site-123",
        "publicationId": "pub-abc",
        "evidence": {"git": {"commit": "a" * 40}},
    }


def test_publication_id_is_deterministic_and_project_scoped() -> None:
    first = build_publication_id("platform/canvas-publishing", "site-123", "a" * 40)
    second = build_publication_id("platform/canvas-publishing", "site-123", "a" * 40)
    other_project = build_publication_id("other/project", "site-123", "a" * 40)

    assert first == second
    assert first.startswith("pub-")
    assert first != other_project


def test_site_publishing_manifest_is_non_secret_and_stable() -> None:
    manifest = site_publishing_manifest(
        site_id="site-123",
        requested_slug="demo",
        title="Demo",
        build_type="static",
        hostname="demo-abc123.canvas.example",
        source_root="/workspace/site",
    )

    assert manifest["version"] == 1
    assert manifest["siteId"] == "site-123"
    assert "token" not in json.dumps(manifest).lower()


def test_canvas_manifest_maps_nextjs_to_managed_build_type(tmp_path: Path) -> None:
    content = tmp_path / "site"
    content.mkdir()
    (content / "package.json").write_text(
        '{"packageManager":"npm@11.0.0"}', encoding="utf-8"
    )
    (content / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (content / "next.config.js").write_text(
        "module.exports = { output: 'standalone' };\n", encoding="utf-8"
    )
    (tmp_path / ".aileron").mkdir()
    (tmp_path / ".aileron" / "canvas.json").write_text(
        json.dumps(
            {
                "version": 1,
                "kind": "nextjs",
                "contentDir": "../site",
                "title": "Demo",
                "routes": [{"path": "/"}],
                "defaultPath": "/",
            }
        ),
        encoding="utf-8",
    )

    manifest, resolved = load_canvas_manifest(tmp_path)

    assert resolved == content
    assert manifest["buildType"] == "nextjs-standalone"


def test_canvas_manifest_rejects_source_root_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "index.html").write_text("<h1>Demo</h1>\n", encoding="utf-8")
    canvas_root = tmp_path / ".aileron"
    canvas_root.mkdir()
    (canvas_root / "site-link").symlink_to(target, target_is_directory=True)
    (canvas_root / "canvas.json").write_text(
        json.dumps(
            {
                "version": 1,
                "kind": "static",
                "contentDir": "site-link",
                "routes": [{"path": "/"}],
                "defaultPath": "/",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SkillError) as error:
        load_canvas_manifest(tmp_path)

    assert error.value.error_code == "PUBLISHING_SOURCE_SYMLINK"


def test_redaction_removes_credentials_from_result_text() -> None:
    value = redact_text(
        "token=gitlab-secret https://oauth2:registry-secret@gitlab.example/repo.git",
        "gitlab-secret",
        "registry-secret",
    )

    assert "gitlab-secret" not in value
    assert "registry-secret" not in value

    json_value = redact_text('{"token":"unknown-token","password": "unknown-password"}')
    assert "unknown-token" not in json_value
    assert "unknown-password" not in json_value


def test_skill_kit_assets_match_release_checksums() -> None:
    _verify_kit_checksums()


def test_skill_kit_release_matches_workspace_configuration(monkeypatch) -> None:
    for key, value in _environment().items():
        monkeypatch.setenv(key, value)

    _verify_kit_release(load_publishing_config())


def test_site_config_drops_unexpected_fields_and_rejects_foreign_hostname(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    write_site_config(
        workspace,
        {
            "siteId": "11111111-1111-4111-8111-111111111111",
            "slug": "demo",
            "title": "Demo",
            "buildType": "static",
            "hostname": "demo-bd7662a5eeb4.canvas.example",
            "token": "must-not-appear",
        },
    )
    loaded = load_site_config(workspace)
    assert "token" not in loaded
    assert "must-not-appear" not in json.dumps(loaded)

    config_path = workspace / ".aileron" / "canvas-publish.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "demo-bd7662a5eeb4.canvas.example",
            "demo-bd7662a5eeb4.other.example",
        ),
        encoding="utf-8",
    )
    with pytest.raises(SkillError) as error:
        resolve_site_config(
            workspace,
            title="Demo",
            build_type="static",
            base_domain="canvas.example",
        )
    assert error.value.error_code == "SITE_HOSTNAME_INVALID"


def test_source_copy_rejects_sensitive_directories(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    (source / ".docker").mkdir(parents=True)
    (source / ".docker" / "config.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SkillError) as error:
        copy_content_tree(source, destination)

    assert error.value.error_code == "PUBLISHING_SOURCE_SECRET"


def test_source_copy_rejects_git_credentials_file(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / ".git-credentials").write_text("https://user:secret@example.com/repo", encoding="utf-8")

    with pytest.raises(SkillError) as error:
        copy_content_tree(source, destination)

    assert error.value.error_code == "PUBLISHING_SOURCE_SECRET"


def test_publish_reuses_only_active_or_successful_pipeline_on_the_same_branch() -> None:
    class FakeGitLab:
        def pipelines_for_sha(self, _project_id: int, _sha: str):
            return [
                {"id": 1, "ref": "sites/site-1", "status": "failed"},
                {"id": 2, "ref": "main", "status": "success"},
                {"id": 3, "ref": "sites/site-1", "status": "running"},
            ]

        def pipeline_variables(self, _project_id: int, _pipeline_id: int):
            return [
                {"key": "AILERON_PUBLISH_TRIGGER", "value": "skill"},
                {"key": "AILERON_PUBLISH_SITE_ID", "value": "site-1"},
                {"key": "AILERON_PUBLISH_PUBLICATION_ID", "value": "pub-abc"},
                {"key": "AILERON_PUBLISH_SOURCE_COMMIT", "value": "a" * 40},
                {"key": "AILERON_PUBLISH_BUILD_TYPE", "value": "static"},
            ]

    pipeline = _reusable_pipeline(
        FakeGitLab(),
        project_id=42,
        branch="sites/site-1",
        source_commit="a" * 40,
        expected_variables={
            "AILERON_PUBLISH_TRIGGER": "skill",
            "AILERON_PUBLISH_SITE_ID": "site-1",
            "AILERON_PUBLISH_PUBLICATION_ID": "pub-abc",
            "AILERON_PUBLISH_SOURCE_COMMIT": "a" * 40,
            "AILERON_PUBLISH_BUILD_TYPE": "static",
        },
    )
    assert pipeline == {"id": 3, "ref": "sites/site-1", "status": "running"}


def test_chart_version_is_immutable_and_shared_by_skill_and_pipeline() -> None:
    publication_id = "pub-" + "a" * 32

    assert chart_version(publication_id) == "0.1.0-" + "a" * 32
    assert package_chart_version(publication_id) == chart_version(publication_id)


def test_argocd_application_is_one_site_with_restricted_sync_policy(monkeypatch) -> None:
    for key, value in _environment().items():
        monkeypatch.setenv(key, value)
    config = load_publishing_config()

    application = desired_application(
        config,
        site_id="11111111-1111-4111-8111-111111111111",
        hostname="demo-abc123.canvas.example",
        publication_id="pub-" + "b" * 32,
        source_commit="c" * 40,
    )

    assert application["spec"]["source"] == {
        "repoURL": f"oci://{config.chart_repository('11111111-1111-4111-8111-111111111111')}",
        "path": ".",
        "targetRevision": "0.1.0-" + "b" * 32,
        "helm": {"releaseName": application["metadata"]["name"]},
    }
    assert application["spec"]["syncPolicy"] == {
        "automated": {"allowEmpty": False, "prune": True, "selfHeal": True},
        "syncOptions": ["CreateNamespace=false"],
    }
    assert application["spec"]["destination"]["namespace"] == "workspace-123"
    assert "token" not in json.dumps(application).lower()


def test_managed_scaffold_uses_skill_trigger_and_has_no_legacy_publish_flow() -> None:
    root = Path(__file__).resolve().parent.parent / "assets" / "user-site-repo"
    scaffold = "\n".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file() and path.suffix != ".pyc"
    )

    assert 'AILERON_PUBLISH_TRIGGER == "skill"' in scaffold
    assert '"helm"' in scaffold and '"push"' in scaffold
    assert "argocd" not in (root / ".gitlab-ci.yml").read_text(encoding="utf-8").lower()
    assert "CANVAS_HARBOR_PASSWORD" not in scaffold
    assert "ownerSlug" not in scaffold


def test_static_pipeline_build_writes_owned_publication_endpoint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text("<h1>Demo</h1>\n", encoding="utf-8")
    manifest_dir = tmp_path / ".aileron" / "publishing"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "site-manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "siteId": "11111111-1111-4111-8111-111111111111",
                "workspaceId": "workspace-123",
                "buildType": "static",
                "hostname": "demo.canvas.example",
                "sourceRoot": "source",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AILERON_PUBLISH_SITE_ID", "11111111-1111-4111-8111-111111111111")
    monkeypatch.setenv("AILERON_PUBLISH_PUBLICATION_ID", "pub-" + "c" * 32)
    monkeypatch.setenv("AILERON_PUBLISH_SOURCE_COMMIT", "d" * 40)
    monkeypatch.setenv("AILERON_PUBLISH_RELEASE_VERSION", "2026.08.04")

    assert build_site_main() == 0
    endpoint = json.loads(
        (tmp_path / ".canvas-build/site/_aileron/publication.json").read_text(
            encoding="utf-8"
        )
    )
    assert endpoint == {
        "buildType": "static",
        "hostname": "demo.canvas.example",
        "publicationId": "pub-" + "c" * 32,
        "releaseVersion": "2026.08.04",
        "schemaVersion": 1,
        "siteId": "11111111-1111-4111-8111-111111111111",
        "sourceCommit": "d" * 40,
    }


def test_status_recovers_previous_verified_publication(monkeypatch, tmp_path: Path) -> None:
    for key, value in _environment().items():
        monkeypatch.setenv(key, value)
    workspace = tmp_path / "workspace"
    old_publication = "pub-" + "e" * 32
    current_publication = "pub-" + "f" * 32
    old_commit = "1" * 40
    current_commit = "2" * 40
    write_site_config(
        workspace,
        {
            "siteId": "11111111-1111-4111-8111-111111111111",
            "slug": "demo",
            "title": "Demo",
            "buildType": "static",
            "hostname": "demo-bd7662a5eeb4.canvas.example",
            "lastSourceCommit": current_commit,
            "lastPublicationId": current_publication,
            "publicationHistory": [
                {
                    "publicationId": old_publication,
                    "sourceCommit": old_commit,
                    "verified": True,
                },
                {
                    "publicationId": current_publication,
                    "sourceCommit": current_commit,
                    "verified": False,
                },
            ],
        },
    )
    config = load_publishing_config()

    class FakeGitLab:
        def __init__(self, _config):
            pass

        def get_project(self, _path):
            return {"id": 42}

        def pipelines_for_sha(self, _project_id, _sha):
            return [{"id": 7, "ref": "sites/11111111-1111-4111-8111-111111111111", "status": "success", "web_url": "https://gitlab.example/p/7"}]

        def pipeline_variables(self, _project_id, _pipeline_id):
            return [
                {"key": "AILERON_PUBLISH_TRIGGER", "value": "skill"},
                {"key": "AILERON_PUBLISH_SITE_ID", "value": "11111111-1111-4111-8111-111111111111"},
                {"key": "AILERON_PUBLISH_PUBLICATION_ID", "value": current_publication},
                {"key": "AILERON_PUBLISH_SOURCE_COMMIT", "value": current_commit},
                {"key": "AILERON_PUBLISH_BUILD_TYPE", "value": "static"},
            ]

    class FakeArgo:
        updates = []

        def __init__(self, _config):
            pass

        def get_application(self, _name):
            application = desired_application(
                config,
                site_id="11111111-1111-4111-8111-111111111111",
                hostname="demo-bd7662a5eeb4.canvas.example",
                publication_id=current_publication,
                source_commit=current_commit,
            )
            application["metadata"]["resourceVersion"] = "9"
            application["status"] = {
                "sync": {"status": "OutOfSync"},
                "health": {"status": "Degraded", "message": "ImagePullBackOff"},
            }
            return application

        def update_application(self, name, payload):
            self.updates.append((name, payload))

    monkeypatch.setattr(status_module, "GitLabClient", FakeGitLab)
    monkeypatch.setattr(status_module, "ArgoCDClient", FakeArgo)
    monkeypatch.setattr(
        status_module,
        "_probe_verification",
        lambda _url, *, ca_pem: {"httpStatus": None, "error": "verification endpoint is unavailable"},
    )

    result = status_module.status_once(config, workspace=workspace)
    saved = load_site_config(workspace)

    assert result["status"] == "RECOVERING"
    assert result["publicationId"] == old_publication
    assert result["deploymentActionId"]
    assert result["evidence"]["recovery"] == {
        "application": config.application_name("11111111-1111-4111-8111-111111111111"),
        "fromPublicationId": current_publication,
        "toPublicationId": old_publication,
        "action": "updated",
    }
    assert len(FakeArgo.updates) == 1
    assert FakeArgo.updates[0][1]["spec"]["source"]["targetRevision"] == chart_version(old_publication)
    assert saved["lastPublicationId"] == old_publication
    assert saved["lastSourceCommit"] == old_commit


def test_status_restores_current_verified_publication_when_application_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    for key, value in _environment().items():
        monkeypatch.setenv(key, value)
    workspace = tmp_path / "workspace"
    publication_id = "pub-" + "a" * 32
    source_commit = "b" * 40
    site_id = "11111111-1111-4111-8111-111111111111"
    hostname = "demo-bd7662a5eeb4.canvas.example"
    write_site_config(
        workspace,
        {
            "siteId": site_id,
            "slug": "demo",
            "title": "Demo",
            "buildType": "static",
            "hostname": hostname,
            "lastSourceCommit": source_commit,
            "lastPublicationId": publication_id,
            "publicationHistory": [
                {
                    "publicationId": publication_id,
                    "sourceCommit": source_commit,
                    "verified": True,
                }
            ],
        },
    )
    config = load_publishing_config()

    class FakeGitLab:
        def __init__(self, _config):
            pass

        def get_project(self, _path):
            return {"id": 42}

        def pipelines_for_sha(self, _project_id, _sha):
            return [{"id": 8, "ref": f"sites/{site_id}", "status": "success"}]

        def pipeline_variables(self, _project_id, _pipeline_id):
            return [
                {"key": "AILERON_PUBLISH_TRIGGER", "value": "skill"},
                {"key": "AILERON_PUBLISH_SITE_ID", "value": site_id},
                {"key": "AILERON_PUBLISH_PUBLICATION_ID", "value": publication_id},
                {"key": "AILERON_PUBLISH_SOURCE_COMMIT", "value": source_commit},
                {"key": "AILERON_PUBLISH_BUILD_TYPE", "value": "static"},
            ]

    class FakeArgo:
        created = []

        def __init__(self, _config):
            pass

        def get_application(self, _name):
            return None

        def create_application(self, application):
            self.created.append(application)

    monkeypatch.setattr(status_module, "GitLabClient", FakeGitLab)
    monkeypatch.setattr(status_module, "ArgoCDClient", FakeArgo)
    monkeypatch.setattr(
        status_module,
        "_probe_verification",
        lambda _url, *, ca_pem: {"httpStatus": None, "error": "verification endpoint is unavailable"},
    )

    result = status_module.status_once(config, workspace=workspace)

    assert result["status"] == "RECOVERING"
    assert result["publicationId"] == publication_id
    assert result["evidence"]["recovery"]["action"] == "created"
    assert len(FakeArgo.created) == 1
    assert FakeArgo.created[0]["spec"]["source"]["targetRevision"] == chart_version(publication_id)


def test_unpublish_rechecks_application_that_appears_after_initial_read(
    monkeypatch,
    tmp_path: Path,
) -> None:
    for key, value in _environment().items():
        monkeypatch.setenv(key, value)
    workspace = tmp_path / "workspace"
    site_id = "11111111-1111-4111-8111-111111111111"
    hostname = "demo-bd7662a5eeb4.canvas.example"
    write_site_config(
        workspace,
        {
            "siteId": site_id,
            "slug": "demo",
            "title": "Demo",
            "buildType": "static",
            "hostname": hostname,
            "lastSourceCommit": "c" * 40,
            "lastPublicationId": "pub-" + "d" * 32,
            "publicationHistory": [],
        },
    )
    config = load_publishing_config()

    class FakeArgo:
        deleted = []
        reads = [
            None,
            {
                **desired_application(
                    config,
                    site_id=site_id,
                    hostname=hostname,
                    publication_id="pub-" + "d" * 32,
                    source_commit="c" * 40,
                ),
                "metadata": {
                    **desired_application(
                        config,
                        site_id=site_id,
                        hostname=hostname,
                        publication_id="pub-" + "d" * 32,
                        source_commit="c" * 40,
                    )["metadata"],
                    "resourceVersion": "7",
                },
            },
            None,
        ]

        def __init__(self, _config):
            pass

        def get_application(self, _name):
            return self.reads.pop(0)

        def delete_application(self, name, *, project=None):
            self.deleted.append((name, project))

    monkeypatch.setattr(unpublish_module, "ArgoCDClient", FakeArgo)
    monkeypatch.setattr(
        unpublish_module,
        "_probe_verification",
        lambda _url, *, ca_pem: {"httpStatus": 404},
    )

    result = unpublish_module.unpublish(workspace)
    saved = load_site_config(workspace)

    assert result["status"] == "UNPUBLISHED"
    assert FakeArgo.deleted == [(config.application_name(site_id), config.argocd_project)]
    assert "lastPublicationId" not in saved
    assert saved.get("publicationHistory", []) == []


def test_rollback_requires_matching_skill_pipeline_identity_and_updates_owned_application(
    monkeypatch,
    tmp_path: Path,
) -> None:
    for key, value in _environment().items():
        monkeypatch.setenv(key, value)
    workspace = tmp_path / "workspace"
    site_id = "11111111-1111-4111-8111-111111111111"
    hostname = "demo-bd7662a5eeb4.canvas.example"
    publication_id = "pub-" + "e" * 32
    source_commit = "f" * 40
    write_site_config(
        workspace,
        {
            "siteId": site_id,
            "slug": "demo",
            "title": "Demo",
            "buildType": "static",
            "hostname": hostname,
            "lastSourceCommit": "1" * 40,
            "lastPublicationId": "pub-" + "1" * 32,
            "publicationHistory": [
                {
                    "publicationId": publication_id,
                    "sourceCommit": source_commit,
                    "verified": True,
                }
            ],
        },
    )
    config = load_publishing_config()

    class FakeGitLab:
        def __init__(self, _config):
            pass

        def get_project(self, _path):
            return {"id": 42}

        def pipelines_for_sha(self, _project_id, _sha):
            return [{"id": 9, "ref": f"sites/{site_id}", "status": "success"}]

        def pipeline_variables(self, _project_id, _pipeline_id):
            return [
                {"key": "AILERON_PUBLISH_TRIGGER", "value": "skill"},
                {"key": "AILERON_PUBLISH_SITE_ID", "value": site_id},
                {"key": "AILERON_PUBLISH_PUBLICATION_ID", "value": publication_id},
                {"key": "AILERON_PUBLISH_SOURCE_COMMIT", "value": source_commit},
                {"key": "AILERON_PUBLISH_BUILD_TYPE", "value": "static"},
            ]

    class FakeArgo:
        updates = []

        def __init__(self, _config):
            pass

        def get_application(self, _name):
            application = desired_application(
                config,
                site_id=site_id,
                hostname=hostname,
                publication_id="pub-" + "1" * 32,
                source_commit="1" * 40,
            )
            application["metadata"]["resourceVersion"] = "11"
            return application

        def update_application(self, name, payload):
            self.updates.append((name, payload))

    monkeypatch.setattr(rollback_module, "GitLabClient", FakeGitLab)
    monkeypatch.setattr(rollback_module, "ArgoCDClient", FakeArgo)

    result = rollback_module.rollback(workspace, publication_id)
    saved = load_site_config(workspace)

    assert result["status"] == "DEPLOYING"
    assert FakeArgo.updates[0][1]["metadata"]["resourceVersion"] == "11"
    assert FakeArgo.updates[0][1]["spec"]["source"]["targetRevision"] == chart_version(publication_id)
    assert saved["lastPublicationId"] == publication_id
