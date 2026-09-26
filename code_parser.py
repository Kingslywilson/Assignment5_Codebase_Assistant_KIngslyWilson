from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from code_loader import SourceFile


@dataclass
class ParsedSymbol:
    """Represents a meaningful source-code structure."""

    name: str
    symbol_type: str
    language: str
    source: str
    module: str
    file_name: str
    signature: str = ""
    parameters: list[str] = field(default_factory=list)
    parent: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    docstring: str = ""
    imports: list[str] = field(default_factory=list)
    route: str | None = None
    http_method: str | None = None
    content: str = ""


@dataclass
class ParsedFile:
    """Represents the parsed structure of one source file."""

    source: str
    language: str
    module: str
    file_name: str
    imports: list[str] = field(default_factory=list)
    symbols: list[ParsedSymbol] = field(default_factory=list)
    content: str = ""


class CodeParser:
    """
    Parse supported source files into meaningful program structures.

    Python files use the built-in AST module.
    JavaScript files use lightweight structural parsing with
    Tree-sitter when available, with a regex fallback for resilience.
    """

    def parse(self, source_file: SourceFile) -> ParsedFile:
        """Parse one SourceFile according to its language."""

        if source_file.language == "python":
            return self._parse_python(source_file)

        if source_file.language == "javascript":
            return self._parse_javascript(source_file)

        return self._parse_generic(source_file)

    def parse_many(
        self,
        source_files: list[SourceFile],
    ) -> list[ParsedFile]:
        """Parse multiple source files."""
        return [self.parse(source_file) for source_file in source_files]

    # ------------------------------------------------------------------
    # Python parsing
    # ------------------------------------------------------------------

    def _parse_python(self, source_file: SourceFile) -> ParsedFile:
        try:
            tree = ast.parse(
                source_file.content,
                filename=source_file.relative_path,
            )
        except SyntaxError as exc:
            return ParsedFile(
                source=source_file.relative_path,
                language="python",
                module=source_file.module,
                file_name=source_file.file_name,
                content=source_file.content,
                symbols=[
                    ParsedSymbol(
                        name=source_file.file_name,
                        symbol_type="file",
                        language="python",
                        source=source_file.relative_path,
                        module=source_file.module,
                        file_name=source_file.file_name,
                        content=source_file.content,
                    )
                ],
            )

        imports = self._extract_python_imports(tree)

        symbols: list[ParsedSymbol] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parent = self._find_python_parent_class(tree, node)

                symbol_type = "method" if parent else "function"

                symbols.append(
                    self._build_python_function_symbol(
                        node=node,
                        source_file=source_file,
                        parent=parent,
                        symbol_type=symbol_type,
                    )
                )

            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    self._build_python_class_symbol(
                        node=node,
                        source_file=source_file,
                    )
                )

        # Detect likely API routes from decorators.
        self._add_python_route_information(symbols, tree, source_file)

        # File-level symbol is useful when no smaller structure captures
        # important module-level behaviour.
        if not symbols:
            symbols.append(
                ParsedSymbol(
                    name=source_file.file_name,
                    symbol_type="module",
                    language="python",
                    source=source_file.relative_path,
                    module=source_file.module,
                    file_name=source_file.file_name,
                    imports=imports,
                    content=source_file.content,
                    start_line=1,
                    end_line=len(source_file.content.splitlines()),
                )
            )

        for symbol in symbols:
            if not symbol.imports:
                symbol.imports = imports

        return ParsedFile(
            source=source_file.relative_path,
            language="python",
            module=source_file.module,
            file_name=source_file.file_name,
            imports=imports,
            symbols=symbols,
            content=source_file.content,
        )

    def _extract_python_imports(
        self,
        tree: ast.AST,
    ) -> list[str]:
        imports: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""

                for alias in node.names:
                    if module:
                        imports.append(f"{module}.{alias.name}")
                    else:
                        imports.append(alias.name)

        return sorted(set(imports))

    def _build_python_function_symbol(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_file: SourceFile,
        parent: str | None,
        symbol_type: str,
    ) -> ParsedSymbol:
        parameters = []

        for argument in (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
        ):
            parameters.append(argument.arg)

        if node.args.vararg:
            parameters.append(f"*{node.args.vararg.arg}")

        if node.args.kwarg:
            parameters.append(f"**{node.args.kwarg.arg}")

        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""

        signature = (
            f"{prefix}{node.name}"
            f"({', '.join(parameters)})"
        )

        content = self._get_python_source_segment(
            source_file.content,
            node,
        )

        return ParsedSymbol(
            name=node.name,
            symbol_type=symbol_type,
            language="python",
            source=source_file.relative_path,
            module=source_file.module,
            file_name=source_file.file_name,
            signature=signature,
            parameters=parameters,
            parent=parent,
            start_line=getattr(node, "lineno", None),
            end_line=getattr(node, "end_lineno", None),
            docstring=ast.get_docstring(node) or "",
            imports=[],
            content=content,
        )

    def _build_python_class_symbol(
        self,
        node: ast.ClassDef,
        source_file: SourceFile,
    ) -> ParsedSymbol:
        bases = []

        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                bases.append("unknown")

        signature = node.name

        if bases:
            signature += f"({', '.join(bases)})"

        content = self._get_python_source_segment(
            source_file.content,
            node,
        )

        return ParsedSymbol(
            name=node.name,
            symbol_type="class",
            language="python",
            source=source_file.relative_path,
            module=source_file.module,
            file_name=source_file.file_name,
            signature=signature,
            parent=None,
            start_line=getattr(node, "lineno", None),
            end_line=getattr(node, "end_lineno", None),
            docstring=ast.get_docstring(node) or "",
            content=content,
        )

    def _find_python_parent_class(
        self,
        tree: ast.AST,
        target: ast.AST,
    ) -> str | None:
        """
        Find the class containing a function/method.

        ast.walk() does not directly expose parent relationships, so we
        recursively inspect class bodies.
        """

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if child is target:
                        return node.name

        return None

    def _add_python_route_information(
        self,
        symbols: list[ParsedSymbol],
        tree: ast.AST,
        source_file: SourceFile,
    ) -> None:
        function_nodes = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        for symbol in symbols:
            if symbol.symbol_type not in {"function", "method"}:
                continue

            node = function_nodes.get(symbol.name)

            if node is None:
                continue

            for decorator in node.decorator_list:
                route = self._extract_python_route(decorator)

                if route is not None:
                    symbol.route = route["path"]
                    symbol.http_method = route["method"]
                    break

    def _extract_python_route(
        self,
        decorator: ast.expr,
    ) -> dict[str, str] | None:
        """
        Detect common FastAPI/Flask-style route decorators.

        Examples:
            @app.get("/users")
            @router.post("/users")
            @app.route("/login", methods=["POST"])
        """

        if not isinstance(decorator, ast.Call):
            return None

        if not isinstance(decorator.func, ast.Attribute):
            return None

        method_name = decorator.func.attr.lower()

        if method_name in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "options",
            "head",
        }:
            if not decorator.args:
                return None

            path_node = decorator.args[0]

            if isinstance(path_node, ast.Constant) and isinstance(
                path_node.value,
                str,
            ):
                return {
                    "path": path_node.value,
                    "method": method_name.upper(),
                }

        if method_name == "route":
            path = None
            methods = None

            if decorator.args:
                first = decorator.args[0]

                if isinstance(first, ast.Constant):
                    if isinstance(first.value, str):
                        path = first.value

            for keyword in decorator.keywords:
                if keyword.arg == "methods":
                    if isinstance(keyword.value, (ast.List, ast.Tuple)):
                        values = []

                        for item in keyword.value.elts:
                            if isinstance(item, ast.Constant):
                                values.append(str(item.value))

                        if values:
                            methods = values[0].upper()

            if path:
                return {
                    "path": path,
                    "method": methods or "ANY",
                }

        return None

    def _get_python_source_segment(
        self,
        source: str,
        node: ast.AST,
    ) -> str:
        try:
            segment = ast.get_source_segment(source, node)

            if segment:
                return segment
        except Exception:
            pass

        lines = source.splitlines()

        start = getattr(node, "lineno", 1) - 1
        end = getattr(
            node,
            "end_lineno",
            getattr(node, "lineno", 1),
        )

        return "\n".join(lines[start:end])

    # ------------------------------------------------------------------
    # JavaScript parsing
    # ------------------------------------------------------------------

    def _parse_javascript(
        self,
        source_file: SourceFile,
    ) -> ParsedFile:
        imports = self._extract_javascript_imports(
            source_file.content
        )

        symbols = self._parse_javascript_with_tree_sitter(
            source_file,
            imports,
        )

        if not symbols:
            symbols = self._parse_javascript_with_regex(
                source_file,
                imports,
            )

        if not symbols:
            symbols.append(
                ParsedSymbol(
                    name=source_file.file_name,
                    symbol_type="module",
                    language="javascript",
                    source=source_file.relative_path,
                    module=source_file.module,
                    file_name=source_file.file_name,
                    imports=imports,
                    content=source_file.content,
                    start_line=1,
                    end_line=len(source_file.content.splitlines()),
                )
            )

        return ParsedFile(
            source=source_file.relative_path,
            language="javascript",
            module=source_file.module,
            file_name=source_file.file_name,
            imports=imports,
            symbols=symbols,
            content=source_file.content,
        )

    def _extract_javascript_imports(
        self,
        content: str,
    ) -> list[str]:
        imports: set[str] = set()

        patterns = [
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'import\s+[\'"]([^\'"]+)[\'"]',
            r'require\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        ]

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                content,
                flags=re.MULTILINE,
            ):
                imports.add(match.group(1))

        return sorted(imports)

    def _parse_javascript_with_tree_sitter(
        self,
        source_file: SourceFile,
        imports: list[str],
    ) -> list[ParsedSymbol]:
        """
        Parse JavaScript with Tree-sitter when the installed version
        exposes the expected parser API.

        If the local Tree-sitter package has a different API version,
        return an empty result and let the regex parser provide a
        lightweight fallback.
        """

        try:
            from tree_sitter import Language, Parser
            import tree_sitter_javascript
        except ImportError:
            return []

        try:
            language = Language(
                tree_sitter_javascript.language()
            )

            parser = Parser(language)
            tree = parser.parse(
                source_file.content.encode("utf-8")
            )

            symbols: list[ParsedSymbol] = []

            self._walk_javascript_tree(
                node=tree.root_node,
                source_file=source_file,
                imports=imports,
                symbols=symbols,
            )

            return symbols

        except Exception:
            return []

    def _walk_javascript_tree(
        self,
        node,
        source_file: SourceFile,
        imports: list[str],
        symbols: list[ParsedSymbol],
        parent: str | None = None,
    ) -> None:
        node_type = node.type

        if node_type in {
            "function_declaration",
            "generator_function_declaration",
        }:
            name_node = node.child_by_field_name("name")

            if name_node is not None:
                name = name_node.text.decode("utf-8")

                parameters = self._tree_sitter_parameters(node)

                symbols.append(
                    ParsedSymbol(
                        name=name,
                        symbol_type="function",
                        language="javascript",
                        source=source_file.relative_path,
                        module=source_file.module,
                        file_name=source_file.file_name,
                        signature=f"{name}({', '.join(parameters)})",
                        parameters=parameters,
                        parent=parent,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        imports=imports,
                        content=node.text.decode("utf-8"),
                    )
                )

        elif node_type in {
            "class_declaration",
            "class",
        }:
            name_node = node.child_by_field_name("name")

            if name_node is not None:
                name = name_node.text.decode("utf-8")

                symbols.append(
                    ParsedSymbol(
                        name=name,
                        symbol_type="class",
                        language="javascript",
                        source=source_file.relative_path,
                        module=source_file.module,
                        file_name=source_file.file_name,
                        signature=name,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        imports=imports,
                        content=node.text.decode("utf-8"),
                    )
                )

                parent = name

        elif node_type in {
            "method_definition",
        }:
            name_node = node.child_by_field_name("name")

            if name_node is not None:
                name = name_node.text.decode("utf-8")
                parameters = self._tree_sitter_parameters(node)

                symbols.append(
                    ParsedSymbol(
                        name=name,
                        symbol_type="method",
                        language="javascript",
                        source=source_file.relative_path,
                        module=source_file.module,
                        file_name=source_file.file_name,
                        signature=f"{name}({', '.join(parameters)})",
                        parameters=parameters,
                        parent=parent,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        imports=imports,
                        content=node.text.decode("utf-8"),
                    )
                )

        for child in node.children:
            self._walk_javascript_tree(
                node=child,
                source_file=source_file,
                imports=imports,
                symbols=symbols,
                parent=parent,
            )

    def _tree_sitter_parameters(self, node) -> list[str]:
        parameters_node = node.child_by_field_name("parameters")

        if parameters_node is None:
            return []

        parameters = []

        for child in parameters_node.named_children:
            parameters.append(
                child.text.decode("utf-8")
            )

        return parameters

    def _parse_javascript_with_regex(
        self,
        source_file: SourceFile,
        imports: list[str],
    ) -> list[ParsedSymbol]:
        """
        Lightweight JavaScript fallback parser.

        This is intentionally structural rather than a replacement
        for Tree-sitter.
        """

        content = source_file.content
        lines = content.splitlines()

        symbols: list[ParsedSymbol] = []

        patterns = [
            (
                "function",
                re.compile(
                    r"^\s*(?:async\s+)?function\s+"
                    r"([A-Za-z_$][\w$]*)\s*\(([^)]*)\)"
                ),
            ),
            (
                "arrow_function",
                re.compile(
                    r"^\s*(?:const|let|var)\s+"
                    r"([A-Za-z_$][\w$]*)\s*=\s*"
                    r"(?:async\s*)?\(([^)]*)\)\s*=>"
                ),
            ),
            (
                "arrow_function_single_parameter",
                re.compile(
                    r"^\s*(?:const|let|var)\s+"
                    r"([A-Za-z_$][\w$]*)\s*=\s*"
                    r"(?:async\s+)?([A-Za-z_$][\w$]*)\s*=>"
                ),
            ),
            (
                "class",
                re.compile(
                    r"^\s*class\s+([A-Za-z_$][\w$]*)"
                ),
            ),
        ]

        for index, line in enumerate(lines):
            for symbol_type, pattern in patterns:
                match = pattern.match(line)

                if not match:
                    continue

                name = match.group(1)

                if symbol_type == "class":
                    parameters = []
                    signature = name
                    actual_type = "class"

                else:
                    raw_parameters = (
                        match.group(2)
                        if match.lastindex and match.lastindex >= 2
                        else ""
                    )

                    parameters = [
                        parameter.strip()
                        for parameter in raw_parameters.split(",")
                        if parameter.strip()
                    ]

                    signature = (
                        f"{name}({', '.join(parameters)})"
                    )

                    actual_type = "function"

                end_line = self._estimate_javascript_end_line(
                    lines,
                    index,
                )

                symbols.append(
                    ParsedSymbol(
                        name=name,
                        symbol_type=actual_type,
                        language="javascript",
                        source=source_file.relative_path,
                        module=source_file.module,
                        file_name=source_file.file_name,
                        signature=signature,
                        parameters=parameters,
                        start_line=index + 1,
                        end_line=end_line,
                        imports=imports,
                        content="\n".join(
                            lines[index:end_line]
                        ),
                    )
                )

                break

        self._add_javascript_routes(
            symbols,
            source_file.content,
        )

        return symbols

    def _estimate_javascript_end_line(
        self,
        lines: list[str],
        start_index: int,
    ) -> int:
        """
        Estimate a JavaScript symbol boundary using brace balance.

        Tree-sitter remains the preferred parser.
        """
        balance = 0
        started = False

        for index in range(start_index, len(lines)):
            line = lines[index]

            balance += line.count("{")
            balance -= line.count("}")

            if "{" in line:
                started = True

            if started and balance <= 0:
                return index + 1

        return min(
            len(lines),
            start_index + 20,
        )

    def _add_javascript_routes(
        self,
        symbols: list[ParsedSymbol],
        content: str,
    ) -> None:
        """
        Detect common Express-style routes.

        Example:
            app.post("/login", login)
        """

        route_patterns = re.findall(
            r"\b(?:app|router)\."
            r"(get|post|put|patch|delete)\s*"
            r"\(\s*[\"']([^\"']+)[\"']\s*,\s*"
            r"([A-Za-z_$][\w$]*)",
            content,
            flags=re.IGNORECASE,
        )

        route_map = {
            function_name: (
                path,
                method.upper(),
            )
            for method, path, function_name
            in route_patterns
        }

        for symbol in symbols:
            if symbol.name in route_map:
                symbol.route, symbol.http_method = route_map[
                    symbol.name
                ]

    # ------------------------------------------------------------------
    # Generic files
    # ------------------------------------------------------------------

    def _parse_generic(
        self,
        source_file: SourceFile,
    ) -> ParsedFile:
        return ParsedFile(
            source=source_file.relative_path,
            language=source_file.language,
            module=source_file.module,
            file_name=source_file.file_name,
            content=source_file.content,
            symbols=[
                ParsedSymbol(
                    name=source_file.file_name,
                    symbol_type="file",
                    language=source_file.language,
                    source=source_file.relative_path,
                    module=source_file.module,
                    file_name=source_file.file_name,
                    start_line=1,
                    end_line=len(
                        source_file.content.splitlines()
                    ),
                    content=source_file.content,
                )
            ],
        )


def parse_codebase(
    source_files: list[SourceFile],
) -> list[ParsedFile]:
    """Convenience function for parsing a complete codebase."""
    parser = CodeParser()
    return parser.parse_many(source_files)