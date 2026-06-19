import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node

INTERESTING_TYPES = [
    "class_definition",
    "function_definition",
    "import_statement",
    "import_from_statement",
]
PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)

content = open("rough4.py", "r").read().encode("utf-8")

tree = parser.parse(content)
root_node = tree.root_node

data = root_node.children
chunks = []


def prepare_metadata(x: Node):
    meta_data = {
        "type": x.type,
        "file": "rough2.py",
        "start_line": x.start_point,
        "end_line": x.end_point,
        "source": x.text,
    }
    return meta_data


def prepare_chunks(data: Node):

    metadata = None
    if data.type in INTERESTING_TYPES:
        metadata = prepare_metadata(data)

    name_node = data.child_by_field_name("name")
    if name_node:
        metadata["name"] = name_node.text

    for child in data.children:
        if child.is_named:
            prepare_chunks(child)

    if metadata:
        chunks.append(metadata)


for x in data:
    prepare_chunks(x)

print(chunks)
