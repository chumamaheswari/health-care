"""
Commits and pushes processed invoice data to a GitHub repository.
"""

import os
import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> str:
    """Run a git command and return stdout. Raises on non-zero exit."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed:\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def push_to_github(
    repo_path: str | Path,
    files_to_add: list[str | Path],
    commit_message: str = "Update processed invoice data",
    branch: str = "main",
) -> None:
    """
    Stage the given files, commit, and push to the remote repository.

    Args:
        repo_path:      Local path to the git repository root.
        files_to_add:   List of file paths (absolute or relative to repo_path) to stage.
        commit_message: Git commit message.
        branch:         Remote branch to push to.
    """
    repo_path = Path(repo_path)

    if not (repo_path / ".git").exists():
        raise ValueError(f"Not a git repository: {repo_path}")

    # Stage each file
    for f in files_to_add:
        _run(["git", "add", str(f)], cwd=repo_path)

    # Check if there is anything to commit
    status = _run(["git", "status", "--porcelain"], cwd=repo_path)
    if not status:
        print("Nothing to commit — output files are unchanged.")
        return

    _run(["git", "commit", "-m", commit_message], cwd=repo_path)
    _run(["git", "push", "origin", branch], cwd=repo_path)
    print(f"Pushed to origin/{branch}: {commit_message}")


def init_repo_if_needed(repo_path: str | Path, remote_url: str | None = None) -> None:
    """
    Initialize a git repo at repo_path if one doesn't already exist.
    Optionally adds a remote origin.
    """
    repo_path = Path(repo_path)
    repo_path.mkdir(parents=True, exist_ok=True)

    if not (repo_path / ".git").exists():
        _run(["git", "init"], cwd=repo_path)
        print(f"Initialized new git repository at {repo_path}")

    if remote_url:
        try:
            _run(["git", "remote", "add", "origin", remote_url], cwd=repo_path)
            print(f"Added remote origin: {remote_url}")
        except RuntimeError:
            # Remote already exists — update it
            _run(["git", "remote", "set-url", "origin", remote_url], cwd=repo_path)
            print(f"Updated remote origin: {remote_url}")
