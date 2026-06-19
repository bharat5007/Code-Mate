import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node


class Indexer:
    def __init__(self):
        self.INTERESTING_TYPES = [
            "class_definition",
            "function_definition",
            "import_statement",
            "import_from_statement",
        ]
        self.parser = Parser(Language(tspython.language()))
        self.chunks = []

    def prepare_metadata(self, node: Node, path: str):
        metadata = {
            "type": node.type,
            "file": path,
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

    def prepare_chunks(self, data: Node, path: str):

        metadata = None
        if data.type in self.INTERESTING_TYPES:
            metadata = self.prepare_metadata(data, path)

        for child in data.children:
            if child.is_named:
                self.prepare_chunks(child, path)

        if metadata:
            self.chunks.append(metadata)

    def initialize_parsing(self, paths):
        for path in paths:
            content = open(path, "r").read().encode("utf-8")
            tree = self.parser.parse(content)
            root_node = tree.root_node

            data = root_node.children
            for x in data:
                self.prepare_chunks(x, str(path))
