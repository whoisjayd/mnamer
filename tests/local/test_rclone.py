"""Tests for rclone utilities."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from mnamer.rclone import (
    check_rclone_installed,
    is_remote_path,
    join_remote_path,
    parse_remote_path,
    rclone_exists,
    rclone_listremotes,
    rclone_lsf,
    rclone_mkdir,
    rclone_move,
    rclone_size,
)


class TestIsRemotePath:
    """Tests for is_remote_path function."""

    def test_remote_path_with_colon(self):
        """Test that paths with remote prefix are detected."""
        assert is_remote_path("gdrive:/movies/test.mkv") is True
        assert is_remote_path("s3:bucket/file.mp4") is True
        assert is_remote_path("dropbox:/videos/show.avi") is True

    def test_local_unix_path(self):
        """Test that local Unix paths are not detected as remote."""
        assert is_remote_path("/home/user/videos/test.mkv") is False
        assert is_remote_path("./relative/path.mp4") is False
        assert is_remote_path("../parent/file.avi") is False

    def test_local_windows_path(self):
        """Test that local Windows paths are not detected as remote."""
        # Windows drive letters should not be detected as remote
        assert is_remote_path("C:/Users/test.mkv") is False
        assert is_remote_path("D:\\Videos\\test.mp4") is False

    def test_path_object(self):
        """Test that Path objects work correctly."""
        assert is_remote_path(Path("/local/path")) is False
        # Remote-like string in Path
        path_str = "remote:/path"
        assert is_remote_path(Path(path_str)) is True


class TestParseRemotePath:
    """Tests for parse_remote_path function."""

    def test_parse_simple_remote_path(self):
        """Test parsing simple remote path."""
        remote, path = parse_remote_path("gdrive:/movies/test.mkv")
        assert remote == "gdrive"
        assert path == "/movies/test.mkv"

    def test_parse_remote_without_slash(self):
        """Test parsing remote path without leading slash."""
        remote, path = parse_remote_path("s3:bucket/file.mp4")
        assert remote == "s3"
        assert path == "bucket/file.mp4"

    def test_parse_local_path(self):
        """Test parsing local path returns empty remote."""
        remote, path = parse_remote_path("/local/path/file.mkv")
        assert remote == ""
        assert path == "/local/path/file.mkv"


class TestJoinRemotePath:
    """Tests for join_remote_path function."""

    def test_join_with_base_path(self):
        """Test joining path components with base path."""
        result = join_remote_path("gdrive:/movies", "action", "test.mkv")
        assert result == "gdrive:/movies/action/test.mkv"

    def test_join_without_base_path(self):
        """Test joining when remote has no base path."""
        result = join_remote_path("gdrive:", "movies", "test.mkv")
        assert result == "gdrive:movies/test.mkv"

    def test_join_single_component(self):
        """Test joining single component."""
        result = join_remote_path("gdrive:/movies", "test.mkv")
        assert result == "gdrive:/movies/test.mkv"


class TestCheckRcloneInstalled:
    """Tests for check_rclone_installed function."""

    def setup_method(self):
        """Reset cache before each test."""
        from mnamer import rclone
        rclone._reset_rclone_cache()

    @patch("subprocess.run")
    def test_rclone_installed(self, mock_run):
        """Test when rclone is installed."""
        mock_run.return_value = MagicMock(returncode=0)
        assert check_rclone_installed() is True

    @patch("subprocess.run")
    def test_rclone_not_found(self, mock_run):
        """Test when rclone is not found."""
        mock_run.side_effect = FileNotFoundError()
        assert check_rclone_installed() is False

    @patch("subprocess.run")
    def test_rclone_timeout(self, mock_run):
        """Test when rclone command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("rclone", 5)
        assert check_rclone_installed() is False


class TestRcloneListremotes:
    """Tests for rclone_listremotes function."""

    @patch("subprocess.run")
    def test_list_remotes_success(self, mock_run):
        """Test listing remotes successfully."""
        mock_result = MagicMock()
        mock_result.stdout = "gdrive:\ns3:\ndropbox:\n"
        mock_run.return_value = mock_result

        remotes = rclone_listremotes()
        assert remotes == ["gdrive", "s3", "dropbox"]

    @patch("subprocess.run")
    def test_list_remotes_empty(self, mock_run):
        """Test when no remotes are configured."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        remotes = rclone_listremotes()
        assert remotes == []

    @patch("subprocess.run")
    def test_list_remotes_failure(self, mock_run):
        """Test when rclone command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "rclone")
        remotes = rclone_listremotes()
        assert remotes == []


class TestRcloneLsf:
    """Tests for rclone_lsf function."""

    @patch("subprocess.run")
    def test_lsf_success(self, mock_run):
        """Test listing files successfully."""
        mock_result = MagicMock()
        mock_result.stdout = "movie1.mkv\nmovie2.mp4\nshow.avi\n"
        mock_run.return_value = mock_result

        files = rclone_lsf("gdrive:/movies")
        assert files == ["movie1.mkv", "movie2.mp4", "show.avi"]

    @patch("subprocess.run")
    def test_lsf_recursive(self, mock_run):
        """Test listing files recursively."""
        mock_result = MagicMock()
        mock_result.stdout = "action/movie.mkv\ncomedy/show.mp4\n"
        mock_run.return_value = mock_result

        files = rclone_lsf("gdrive:/movies", recursive=True)
        assert "action/movie.mkv" in files

        # Check that --recursive flag was passed
        call_args = mock_run.call_args[0][0]
        assert "--recursive" in call_args

    @patch("subprocess.run")
    def test_lsf_failure(self, mock_run):
        """Test when listing fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "rclone")
        files = rclone_lsf("gdrive:/movies")
        assert files == []


class TestRcloneSize:
    """Tests for rclone_size function."""

    @patch("subprocess.run")
    def test_size_success(self, mock_run):
        """Test getting file size successfully."""
        mock_result = MagicMock()
        mock_result.stdout = '{"bytes": 1048576}'
        mock_run.return_value = mock_result

        size = rclone_size("gdrive:/movies/test.mkv")
        assert size == 1048576

    @patch("subprocess.run")
    def test_size_failure(self, mock_run):
        """Test when size command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "rclone")
        size = rclone_size("gdrive:/movies/test.mkv")
        assert size == 0

    @patch("subprocess.run")
    def test_size_invalid_json(self, mock_run):
        """Test when rclone returns invalid JSON."""
        mock_result = MagicMock()
        mock_result.stdout = "invalid json"
        mock_run.return_value = mock_result

        size = rclone_size("gdrive:/movies/test.mkv")
        assert size == 0


class TestRcloneExists:
    """Tests for rclone_exists function."""

    @patch("mnamer.rclone.rclone_lsf")
    def test_exists_true(self, mock_lsf):
        """Test when file exists."""
        mock_lsf.return_value = ["test.mkv", "other.mp4"]
        assert rclone_exists("gdrive:/movies/test.mkv") is True

    @patch("mnamer.rclone.rclone_lsf")
    def test_exists_false(self, mock_lsf):
        """Test when file does not exist."""
        mock_lsf.return_value = ["other.mp4"]
        assert rclone_exists("gdrive:/movies/test.mkv") is False

    @patch("mnamer.rclone.rclone_lsf")
    def test_exists_exception(self, mock_lsf):
        """Test when rclone command fails."""
        mock_lsf.side_effect = Exception("rclone error")
        assert rclone_exists("gdrive:/movies/test.mkv") is False


class TestRcloneMove:
    """Tests for rclone_move function."""

    @patch("subprocess.run")
    def test_move_success(self, mock_run):
        """Test moving file successfully."""
        mock_run.return_value = MagicMock(returncode=0)
        assert rclone_move("gdrive:/old/test.mkv", "gdrive:/new/test.mkv") is True

    @patch("subprocess.run")
    def test_move_failure(self, mock_run):
        """Test when move fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "rclone")
        assert rclone_move("gdrive:/old/test.mkv", "gdrive:/new/test.mkv") is False

    @patch("subprocess.run")
    def test_move_local_to_remote(self, mock_run):
        """Test moving from local to remote."""
        mock_run.return_value = MagicMock(returncode=0)
        assert rclone_move("/local/test.mkv", "gdrive:/remote/test.mkv") is True


class TestRcloneMkdir:
    """Tests for rclone_mkdir function."""

    @patch("subprocess.run")
    def test_mkdir_success(self, mock_run):
        """Test creating directory successfully."""
        mock_run.return_value = MagicMock(returncode=0)
        assert rclone_mkdir("gdrive:/new/directory") is True

    @patch("subprocess.run")
    def test_mkdir_failure(self, mock_run):
        """Test when mkdir fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "rclone")
        assert rclone_mkdir("gdrive:/new/directory") is False
