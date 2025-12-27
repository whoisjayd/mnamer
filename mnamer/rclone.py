"""Utilities for working with remote paths via rclone."""

import json
import re
import subprocess
from pathlib import Path, PurePosixPath


def is_remote_path(path: str | Path) -> bool:
    """
    Check if a path is a remote rclone path.

    Remote paths typically follow the format: remote_name:path/to/file
    where remote_name is configured in rclone config.

    Args:
        path: Path to check

    Returns:
        True if path appears to be a remote rclone path

    Note:
        The detection uses a regex pattern that matches paths with a colon
        but excludes Windows drive letters (single character followed by colon).
        Pattern: ^[^/\\]{2,}: matches at least 2 non-slash characters before a colon.
    """
    path_str = str(path)
    # Remote paths contain a colon not associated with Windows drive letters
    # Pattern matches: "remote:" or "remote:path" but not "C:" or "C:\path"
    return bool(re.match(r"^[^/\\]{2,}:", path_str))


def check_rclone_installed() -> bool:
    """
    Check if rclone is installed and available in PATH.

    Returns:
        True if rclone is installed, False otherwise
    """
    try:
        subprocess.run(
            ["rclone", "version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
        return True
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def rclone_listremotes() -> list[str]:
    """
    Get list of configured rclone remotes.

    Returns:
        List of remote names (without trailing colons)
    """
    try:
        result = subprocess.run(
            ["rclone", "listremotes"],
            capture_output=True,
            check=True,
            text=True,
            timeout=10,
        )
        remotes = [
            line.rstrip(":") for line in result.stdout.strip().split("\n") if line
        ]
        return remotes
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return []


def parse_remote_path(path: str | Path) -> tuple[str, str]:
    """
    Parse a remote path into remote name and remote path components.

    Args:
        path: Remote path in format remote:path/to/file

    Returns:
        Tuple of (remote_name, remote_path)

    Example:
        >>> parse_remote_path("gdrive:/movies/test.mkv")
        ("gdrive", "/movies/test.mkv")
    """
    path_str = str(path)
    if ":" in path_str:
        parts = path_str.split(":", 1)
        return parts[0], parts[1]
    return "", path_str


def rclone_lsf(
    remote_path: str | Path, recursive: bool = False, files_only: bool = True
) -> list[str]:
    """
    List files in a remote path using rclone lsf.

    Args:
        remote_path: Remote path to list
        recursive: If True, list recursively
        files_only: If True, only list files (not directories)

    Returns:
        List of file paths relative to remote_path
    """
    cmd = ["rclone", "lsf"]

    if recursive:
        cmd.append("--recursive")
    if files_only:
        cmd.append("--files-only")

    cmd.append(str(remote_path))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            text=True,
            timeout=60,
        )
        files = [
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        ]
        return files
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return []


def rclone_size(remote_path: str | Path) -> int:
    """
    Get the size of a remote file in bytes.

    Args:
        remote_path: Remote file path

    Returns:
        File size in bytes, or 0 if not found
    """
    cmd = ["rclone", "size", str(remote_path), "--json"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        return int(data.get("bytes", 0))
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ):
        return 0


def rclone_exists(remote_path: str | Path) -> bool:
    """
    Check if a remote file or directory exists.

    Args:
        remote_path: Remote path to check

    Returns:
        True if path exists, False otherwise
    """
    # Use lsf to check if the file exists
    remote_str = str(remote_path)
    remote_name, path_part = parse_remote_path(remote_str)

    if not path_part:
        return False

    # Get parent directory and filename
    pure_path = PurePosixPath(path_part)
    parent = str(pure_path.parent)
    filename = pure_path.name

    # Construct parent remote path
    if parent == ".":
        parent_remote = f"{remote_name}:"
    else:
        parent_remote = f"{remote_name}:{parent}"

    try:
        files = rclone_lsf(parent_remote, recursive=False, files_only=False)
        return filename in files
    except Exception:
        return False


def rclone_move(source: str | Path, destination: str | Path) -> bool:
    """
    Move a file using rclone.

    Args:
        source: Source path (can be local or remote)
        destination: Destination path (can be local or remote)

    Returns:
        True if move was successful, False otherwise
    """
    cmd = ["rclone", "moveto", str(source), str(destination)]

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=300,  # 5 minutes for large files
        )
        return True
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def rclone_mkdir(remote_path: str | Path) -> bool:
    """
    Create a directory on remote.

    Args:
        remote_path: Remote directory path to create

    Returns:
        True if successful, False otherwise
    """
    cmd = ["rclone", "mkdir", str(remote_path)]

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=30,
        )
        return True
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def join_remote_path(remote_base: str, *parts: str) -> str:
    """
    Join remote path components.

    Args:
        remote_base: Base remote path (e.g., "gdrive:/movies")
        *parts: Additional path components

    Returns:
        Joined remote path
    """
    remote_name, base_path = parse_remote_path(remote_base)

    # Use PurePosixPath for remote paths (most remotes use POSIX-style paths)
    if base_path:
        joined = PurePosixPath(base_path).joinpath(*parts)
    else:
        joined = PurePosixPath(*parts)

    return f"{remote_name}:{joined}"
