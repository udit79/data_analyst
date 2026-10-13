"""Artifact transfer helpers for the managed sandbox walkthrough."""

import base64
import json
from pathlib import PurePosixPath

WORKSPACE_ROOT = PurePosixPath("/workspace")
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts"


def _artifact_path(path: str) -> PurePosixPath:
    """Accept only workspace artifact paths and normalize them for local saving."""
    requested = PurePosixPath(path)
    if requested.is_absolute():
        try:
            relative = requested.relative_to(WORKSPACE_ROOT)
        except ValueError as error:
            raise ValueError(
                "Only files under /workspace/artifacts can be downloaded"
            ) from error
    else:
        relative = requested
    if ".." in relative.parts or not relative.parts or relative.parts[0] != "artifacts":
        raise ValueError("Only files under /workspace/artifacts can be downloaded")
    return relative


def create_artifact_download_tool():
    """Create a managed tool that returns sandbox files as base64 JSON."""
    from langchain.tools import tool
    from managed_deepagents import ManagedToolRuntime

    @tool
    def download_artifacts(paths: list[str], runtime: ManagedToolRuntime) -> str:
        """Download generated sandbox files for the local CLI.

        Args:
            paths: Paths under `/workspace/artifacts` to return to the CLI.
        """
        if runtime.backend is None:
            raise RuntimeError("This agent run has no sandbox backend")

        sandbox_paths = [str(WORKSPACE_ROOT / _artifact_path(path)) for path in paths]
        downloads = runtime.backend.download_files(sandbox_paths)
        files = []
        for path, download in zip(sandbox_paths, downloads, strict=True):
            if download.error:
                raise RuntimeError(
                    f"Could not download sandbox artifact {path}: {download.error}"
                )
            if download.content is None:
                raise RuntimeError(f"Sandbox returned no content for artifact {path}")
            files.append(
                {
                    "path": str(_artifact_path(path)),
                    "content_base64": base64.b64encode(download.content).decode(
                        "ascii"
                    ),
                }
            )
        return json.dumps({"artifacts": files})

    return download_artifacts


def create_local_artifact_download_tool(backend):
    """Create an artifact tool bound to one isolated local Docker workspace."""
    from langchain.tools import ToolRuntime, tool

    @tool
    def download_artifacts(paths: list[str], runtime: ToolRuntime) -> str:
        """Return requested generated files under `/workspace/artifacts`."""
        sandbox_paths = [str(WORKSPACE_ROOT / _artifact_path(path)) for path in paths]
        downloads = backend.download_files(sandbox_paths)
        files = []
        for path, download in zip(sandbox_paths, downloads, strict=True):
            if download.error or download.content is None:
                raise RuntimeError(
                    f"Could not download sandbox artifact {path}: {download.error}"
                )
            files.append(
                {
                    "path": str(_artifact_path(path)),
                    "content_base64": base64.b64encode(download.content).decode(
                        "ascii"
                    ),
                }
            )
        return json.dumps({"artifacts": files})

    return download_artifacts
