from pathlib import Path

from indexer import Indexer
from retriver import Retriver

repo_path = "/Users/bharat.goyal1/code_mate"

exclude_dirs = {".venv"}
exclude_files = {"setup.py"}

paths = []

for file in Path(repo_path).rglob("*.py"):
    if any(part in exclude_dirs for part in file.parts):
        continue

    if file.name in exclude_files:
        continue

    paths.append(file)

indexer = Indexer()
indexer.initialize_parsing(paths)
retriver = Retriver(indexer.updated_chunks, 384)


# after update
indexer.update_tree(paths)
if indexer.updated_chunks:
    retriver.bm25_remove_chunks(paths)
    retriver.bm25_add_chunks(indexer.updated_chunks)
    retriver.faiss_add_chunks(indexer.updated_chunks, indexer.removed_chunks)


############################## TO FOLLOW GITIGNORE ############################
# repo = Path(repo_path)
# with open(repo / ".gitignore") as f:
#     spec = pathspec.PathSpec.from_lines(
#         pathspec.patterns.GitWildMatchPattern,
#         f
#     )

# for file in repo.rglob("*.py"):
#     relative = file.relative_to(repo)

#     if spec.match_file(str(relative)):
#         continue

#     print(file)
