"""Artifact transfer helpers for the managed sandbox walkthrough."""

import base64
import json
from pathlib import PurePosixPath


def create_artifact_download_tool():
    """Create a managed tool that returns sandbox files as base64 JSON."""
    from langchain.tools import tool
    from managed_deepagents import ManagedToolRuntime

    @tool
    def download_artifacts(paths: list[str], runtime: ManagedToolRuntime) -> str:
        """Download generated sandbox files for the local CLI.

        Args:
            paths: Sandbox file paths to return to the CLI.
        """
        if runtime.backend is None:
            raise RuntimeError("This agent run has no sandbox backend")

        downloads = runtime.backend.download_files(paths)
        files = []
        for path, download in zip(paths, downloads, strict=True):
            if download.error:
                raise RuntimeError(f"Could not download sandbox artifact {path}: {download.error}")
            if download.content is None:
                raise RuntimeError(f"Sandbox returned no content for artifact {path}")
            files.append(
                {
                    "path": str(PurePosixPath(path)),
                    "content_base64": base64.b64encode(download.content).decode("ascii"),
                }
            )
        return json.dumps({"artifacts": files})

    return download_artifacts
