from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class SourceFile:
    """Represents a source file selected for codebase analysis."""

    path: Path
    relative_path: str
    file_name: str
    language: str
    module: str
    file_type: str
    content: str


@dataclass
class CodebaseLoader:
    """
    Discover and load supported project files.

    The loader deliberately excludes common dependency, build, cache,
    IDE, and credential locations before reading source files.
    """

    supported_extensions: set[str] = field(
        default_factory=lambda: {
            ".py",
            ".js",
            ".json",
            ".md",
            ".txt",
            ".yaml",
            ".yml",
        }
    )

    ignored_directories: set[str] = field(
        default_factory=lambda: {
            ".git",
            "__pycache__",
            "venv",
            ".venv",
            "node_modules",
            "dist",
            "build",
            "coverage",
            ".pytest_cache",
            ".idea",
            ".vscode",
        }
    )

    ignored_file_names: set[str] = field(
        default_factory=lambda: {
            ".env",
            ".env.local",
            ".env.development",
            ".env.production",
            "credentials.json",
            "secrets.json",
        }
    )

    ignored_suffixes: set[str] = field(
        default_factory=lambda: {
            ".pem",
            ".key",
            ".log",
            ".tmp",
            ".pyc",
            ".pyo",
            ".so",
            ".dll",
            ".exe",
            ".bin",
            ".db",
            ".sqlite",
        }
    )

    def discover_files(self, project_path: str | Path) -> list[Path]:
        """
        Discover files that are safe and relevant for code understanding.

        Returns paths only; file content is loaded separately.
        """
        root = self._validate_project_path(project_path)

        discovered: list[Path] = []

        for current_root, directories, files in __import__("os").walk(root):
            current_path = Path(current_root)

            # Modify directories in-place so os.walk does not descend into
            # ignored directories.
            directories[:] = sorted(
                directory
                for directory in directories
                if not self._is_ignored_directory(directory)
            )

            for file_name in sorted(files):
                file_path = current_path / file_name

                if self._should_ignore_file(file_path):
                    continue

                if file_path.suffix.lower() not in self.supported_extensions:
                    continue

                discovered.append(file_path)

        return sorted(discovered)

    def load_project(self, project_path: str | Path) -> list[SourceFile]:
        """
        Discover and load all supported files from a project.

        Relative project paths are stored in metadata rather than
        exposing the user's local absolute path.
        """
        root = self._validate_project_path(project_path)
        files = self.discover_files(root)

        source_files: list[SourceFile] = []

        for file_path in files:
            content = self._read_text_file(file_path)

            if not content.strip():
                continue

            relative_path = file_path.relative_to(root).as_posix()

            source_files.append(
                SourceFile(
                    path=file_path,
                    relative_path=relative_path,
                    file_name=file_path.name,
                    language=self._detect_language(file_path),
                    module=self._detect_module(relative_path),
                    file_type=file_path.suffix.lower().lstrip("."),
                    content=content,
                )
            )

        return source_files

    def iter_project_files(
        self,
        project_path: str | Path,
    ) -> Iterator[SourceFile]:
        """Yield loaded source files one at a time."""
        for source_file in self.load_project(project_path):
            yield source_file

    def _validate_project_path(self, project_path: str | Path) -> Path:
        root = Path(project_path).expanduser().resolve()

        if not root.exists():
            raise FileNotFoundError(
                f"Project path does not exist: {project_path}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Project path is not a directory: {project_path}"
            )

        return root

    def _is_ignored_directory(self, directory_name: str) -> bool:
        return directory_name in self.ignored_directories

    def _should_ignore_file(self, file_path: Path) -> bool:
        file_name = file_path.name.lower()

        # Exact credential/secret names.
        if file_name in {
            name.lower() for name in self.ignored_file_names
        }:
            return True

        # Any .env variant is excluded.
        if file_name == ".env" or file_name.startswith(".env."):
            return True

        # Credential and private-key style files.
        if file_name.endswith(
            (".pem", ".key", ".crt", ".p12", ".pfx")
        ):
            return True

        # Generated, temporary, compiled, log, and binary-like files.
        if file_path.suffix.lower() in self.ignored_suffixes:
            return True

        return False

    def _read_text_file(self, file_path: Path) -> str:
        """
        Read text safely.

        UTF-8 is preferred, with a small fallback for projects containing
        legacy text files.
        """
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

    def _detect_language(self, file_path: Path) -> str:
        extension = file_path.suffix.lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".json": "json",
            ".md": "markdown",
            ".txt": "text",
            ".yaml": "yaml",
            ".yml": "yaml",
        }

        return language_map.get(extension, "unknown")

    def _detect_module(self, relative_path: str) -> str:
        """
        Derive a useful module/folder name from the relative project path.

        Example:
            app/services/auth_service.py -> services
            src/auth/token.js -> auth
            main.py -> root
        """
        path = Path(relative_path)
        parent_parts = path.parent.parts

        if not parent_parts:
            return "root"

        return parent_parts[-1]


def load_codebase(project_path: str | Path) -> list[SourceFile]:
    """
    Convenience function for loading a project.

    The rest of the application can call this without needing to know
    the loader implementation details.
    """
    loader = CodebaseLoader()
    return loader.load_project(project_path)