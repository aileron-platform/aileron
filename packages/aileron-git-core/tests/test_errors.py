from aileron_git_core.errors import (
    GitCoreError,
    GitOperationInProgressError,
    GitStaleLockError,
)


def test_stale_lock_error_is_operation_in_progress_subclass():
    err = GitStaleLockError("workspace:abc")
    assert isinstance(err, GitOperationInProgressError)
    assert isinstance(err, GitCoreError)
    assert err.key == "workspace:abc"


def test_stale_lock_error_distinguishable_from_plain_collision():
    collision = GitOperationInProgressError("workspace:abc")
    stale = GitStaleLockError("workspace:abc")
    assert not isinstance(collision, GitStaleLockError)
    assert isinstance(stale, GitStaleLockError)
