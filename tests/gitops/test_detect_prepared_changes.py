import subprocess

import pytest


def git(repo, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def create_repository(repo):
    git(repo, "init")
    git(repo, "config", "user.name", "GitOps Tests")
    git(repo, "config", "user.email", "gitops-tests@example.invalid")

    (repo / "README.md").write_text(
        "Initial repository\n",
        encoding="utf-8",
    )

    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial commit")

    return git(repo, "rev-parse", "HEAD")


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)

    return git(repo, "rev-parse", "HEAD")


def test_is_prepared_file_accepts_prepared_manifest(
    prepared_detector,
):
    assert prepared_detector.is_prepared_file(
        "gitops/applications/my-app/prepared/application.yaml"
    )


def test_is_prepared_file_rejects_dev_manifest(
    prepared_detector,
):
    assert not prepared_detector.is_prepared_file(
        "gitops/applications/my-app/dev/application.yaml"
    )


def test_is_prepared_file_rejects_unrelated_prepared_directory(
    prepared_detector,
):
    assert not prepared_detector.is_prepared_file(
        "gitops/applications/my-app/dev/prepared/application.yaml"
    )


@pytest.mark.parametrize(
    ("operation", "expected_status"),
    [
        ("add", "A"),
        ("modify", "M"),
        ("delete", "D"),
        ("rename", "R"),
    ],
)
def test_get_prepared_changes_detects_git_operations(
    tmp_path,
    prepared_detector,
    operation,
    expected_status,
):
    repo = tmp_path

    prepared_dir = (
        repo
        / "gitops"
        / "applications"
        / "my-app"
        / "prepared"
    )

    old_file = prepared_dir / "application.yaml"
    new_file = prepared_dir / "application-renamed.yaml"

    if operation in ("modify", "delete", "rename"):
        old_file.parent.mkdir(parents=True)
        old_file.write_text(
            "apiVersion: v1\nkind: ConfigMap\n",
            encoding="utf-8",
        )

    base = create_repository(repo)

    if operation == "add":
        old_file.parent.mkdir(parents=True)
        old_file.write_text(
            "apiVersion: v1\nkind: ConfigMap\n",
            encoding="utf-8",
        )

    elif operation == "modify":
        old_file.write_text(
            "apiVersion: v1\nkind: Secret\n",
            encoding="utf-8",
        )

    elif operation == "delete":
        old_file.unlink()

    elif operation == "rename":
        git(
            repo,
            "mv",
            str(old_file.relative_to(repo)),
            str(new_file.relative_to(repo)),
        )

    head = commit_all(repo, f"{operation} prepared manifest")

    prepared_detector.ROOT = repo

    changes = prepared_detector.get_prepared_changes(
        base,
        head,
    )

    assert len(changes) == 1
    assert changes[0][0].startswith(expected_status)

    if operation == "rename":
        assert changes[0][1].endswith("application.yaml")
        assert changes[0][2].endswith("application-renamed.yaml")





def test_get_prepared_changes_ignores_dev_changes(
    tmp_path,
    prepared_detector,
):
    repo = tmp_path
    base = create_repository(repo)

    dev_dir = (
        repo
        / "gitops"
        / "applications"
        / "my-app"
        / "dev"
    )

    dev_dir.mkdir(parents=True)

    (dev_dir / "application.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\n",
        encoding="utf-8",
    )

    head = commit_all(repo, "modify dev manifest")

    prepared_detector.ROOT = repo

    assert prepared_detector.get_prepared_changes(
        base,
        head,
    ) == []


def test_get_prepared_changes_returns_empty_without_changes(
    tmp_path,
    prepared_detector,
):
    repo = tmp_path
    commit = create_repository(repo)

    prepared_detector.ROOT = repo

    assert prepared_detector.get_prepared_changes(
        commit,
        commit,
    ) == []


@pytest.mark.parametrize(
    "event_name",
    ["pull_request", "push"],
)
def test_get_comparison_uses_github_sha_environment(
    monkeypatch,
    prepared_detector,
    event_name,
):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event_name)
    monkeypatch.setenv("BASE_SHA", "a" * 40)
    monkeypatch.setenv("HEAD_SHA", "b" * 40)

    assert prepared_detector.get_comparison() == (
        "a" * 40,
        "b" * 40,
    )


def test_get_comparison_rejects_zero_base_sha(
    monkeypatch,
    prepared_detector,
):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("BASE_SHA", "0" * 40)
    monkeypatch.setenv("HEAD_SHA", "b" * 40)

    assert prepared_detector.get_comparison() is None


def test_get_comparison_rejects_unsupported_event(
    monkeypatch,
    prepared_detector,
):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")

    assert prepared_detector.get_comparison() is None


def test_workflow_dispatch_compares_previous_commit(
    tmp_path,
    monkeypatch,
    prepared_detector,
):
    repo = tmp_path
    create_repository(repo)

    (repo / "README.md").write_text(
        "Second commit\n",
        encoding="utf-8",
    )

    head = commit_all(repo, "second commit")
    base = git(repo, "rev-parse", "HEAD^")

    prepared_detector.ROOT = repo
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")

    assert prepared_detector.get_comparison() == (
        base,
        head,
    )


def test_workflow_dispatch_without_parent_returns_none(
    tmp_path,
    monkeypatch,
    prepared_detector,
):
    repo = tmp_path
    create_repository(repo)

    prepared_detector.ROOT = repo
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")

    assert prepared_detector.get_comparison() is None