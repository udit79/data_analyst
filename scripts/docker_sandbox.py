"""Small, network-isolated Docker backend for deterministic EDA rendering."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)


class DockerSandbox:
    """Map ``/workspace`` to a temporary host directory and run only the renderer."""

    def __init__(self, image: str | None = None, root_dir: Path | None = None) -> None:
        self.image = image or os.getenv(
            "SANDBOX_DOCKER_IMAGE", "data-agent-eda:checkpoint"
        )
        workspace_parent = root_dir or (Path.cwd() / "artifacts" / "web")
        workspace_parent.mkdir(parents=True, exist_ok=True)
        self._temporary = tempfile.TemporaryDirectory(
            prefix="data-agent-", dir=workspace_parent
        )
        self.root = Path(self._temporary.name).resolve()

    @staticmethod
    def _path(path: str) -> PurePosixPath:
        parsed = PurePosixPath(path)
        if (
            not parsed.is_absolute()
            or parsed.parts[:2] != ("/", "workspace")
            or ".." in parsed.parts
        ):
            raise ValueError("Sandbox paths must stay under /workspace")
        return parsed

    def _host_path(self, path: str) -> Path:
        relative = self._path(path).relative_to("/workspace")
        destination = (self.root / Path(*relative.parts)).resolve()
        if not destination.is_relative_to(self.root):
            raise ValueError("Sandbox path escapes its workspace")
        return destination

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses = []
        for path, content in files:
            try:
                destination = self._host_path(path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                responses.append(FileUploadResponse(path=path))
            except (OSError, ValueError) as error:
                responses.append(FileUploadResponse(path=path, error=str(error)))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses = []
        for path in paths:
            try:
                source = self._host_path(path)
                responses.append(
                    FileDownloadResponse(path=path, content=source.read_bytes())
                )
            except FileNotFoundError:
                responses.append(
                    FileDownloadResponse(path=path, error="file_not_found")
                )
            except (OSError, ValueError) as error:
                responses.append(FileDownloadResponse(path=path, error=str(error)))
        return responses

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        if command.strip() != "python /workspace/eda_renderer.py":
            return ExecuteResponse(output="Command is not allowed", exit_code=126)
        docker_command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--tmpfs",
            "/tmp:rw,nosuid,size=1g",
            "--shm-size",
            "1g",
            "--memory",
            "3g",
            "--cpus",
            "2",
            "--pids-limit",
            "512",
            "--mount",
            f"type=bind,source={self.root},target=/workspace",
            "--workdir",
            "/workspace",
            "-e",
            "HOME=/tmp",
            "-e",
            "XDG_CONFIG_HOME=/tmp/.config",
            "-e",
            "BROWSER_PATH=/usr/bin/chromium",
            self.image,
            "python",
            "/workspace/eda_renderer.py",
        ]
        try:
            result = subprocess.run(
                docker_command,
                capture_output=True,
                text=True,
                timeout=timeout or 180,
                check=False,
            )
            return ExecuteResponse(
                output=(result.stdout + result.stderr)[-12000:],
                exit_code=result.returncode,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return ExecuteResponse(output=str(error), exit_code=1)
