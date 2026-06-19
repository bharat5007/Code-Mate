import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)

content = open("rough2.py", "r").read().encode("utf-8")

tree = parser.parse(content)
root_node = tree.root_node

x = root_node.children
# print(root_node.children[1].text)
for i in x:
    print(f"{i.text}     {i.type}      {len(i.children)}")
    print()
    if i.type == "function_definition":
        for child in i.children:
            print(child.type, "-->", child.text)

    print()
    print()

# print("Root node type:", root_node.children)
print()
# print(f"<<<<<<<<<<<< {root_node}")  # poora syntax tree S-expression form mein