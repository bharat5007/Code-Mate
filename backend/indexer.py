import uuid
import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node


class Indexer:
    def __init__(self, paths):
        self.INTERESTING_TYPES = [
            "class_definition",
            "function_definition",
            "import_statement",
            "import_from_statement",
        ]
        self.parser = Parser(Language(tspython.language()))
        self.path_tree_mapping = {}
        self.paths = None
        self.chunks = {}
        self.updated_chunks = []
        self.removed_chunks = []
        self.initialize_parsing(paths)

    def prepare_metadata(self, node: Node, path: str):
        metadata = {
            "id": uuid.uuid4().int % (2**63),
            "file": path,
            "type": node.type,
            "start_line": node.start_point[0],
            "end_line": node.end_point[0],
            "source": node.text.decode("utf-8"),
        }

        # Store name
        name_node = node.child_by_field_name("name")
        if name_node:
            metadata["name"] = name_node.text.decode("utf-8")

        # Store sub_function names
        if node.type == "class_definition":
            sub_functions = []
            body_node = node.child_by_field_name("body")
            for child in body_node.children:
                name_node = child.child_by_field_name("name")
                if name_node:
                    sub_functions.append(name_node.text.decode("utf-8"))

            metadata["sub_functions"] = sub_functions

        # Store substrings
        body = node.child_by_field_name("body")
        if body:
            first = body.children[0]
            if (
                first.type == "expression_statement"
                and first.children[0].type == "string"
            ):
                metadata["doc_string"] = first.text.decode("utf-8")

        return metadata

    def prepare_chunks(self, data: Node, path: str, is_updated: bool = True):
        metadata = None
        if data.type in self.INTERESTING_TYPES:
            metadata = self.prepare_metadata(data, path)

        for child in data.children:
            if child.is_named:
                self.prepare_chunks(child, path, is_updated)

        if metadata:
            if path not in self.chunks:
                self.chunks[path] = []
            self.chunks[path].append(metadata)

            if is_updated:
                self.updated_chunks.append(metadata)

    def initialize_parsing(self, paths: list, is_updated: bool = True):
        self.paths = paths
        for path in paths:
            content = open(path, "r").read().encode("utf-8")
            tree = self.parser.parse(content)
            self.path_tree_mapping[path] = tree
            root_node = tree.root_node

            data = root_node.children
            for x in data:
                self.prepare_chunks(x, str(path), is_updated)

    def update_chunks(self, path):
        # For sake of simplicity will be update whole chunk of that file for now
        self.chunks.pop(path, None)
        self.initialize_parsing([path])

    def update_tree(self, paths):
        self.updated_chunks = []
        self.removed_chunks = []
        # Files are removed
        removed_paths = set(self.paths) - set(paths)
        for path in removed_paths:
            self.removed_chunks.extend(self.chunks[path])
            self.chunks.pop(path)

        for path in paths:
            content = open(path, "r").read().encode("utf-8")
            tree = self.parser.parse(content)

            # New fils is added
            if self.path_tree_mapping.get(path) is None:
                root_node = tree.root_node
                data = root_node.children
                for x in data:
                    self.prepare_chunks(x, str(path))

            # File is updated
            elif tree.root_node.text != self.path_tree_mapping[path].root_node.text:
                self.update_chunks(path)

        # update current path list
        self.paths = paths
