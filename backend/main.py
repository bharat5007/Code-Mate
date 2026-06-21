from pathlib import Path

from indexer import Indexer
from retriver import Retriver

repo_path = "/Users/bharat.goyal1/code_mate"

exclude_dirs = {".venv"}
exclude_files = {"setup.py"}

paths = []


def fetch_python_files_path():
    for file in Path(repo_path).rglob("*.py"):
        if any(part in exclude_dirs for part in file.parts):
            continue

        if file.name in exclude_files:
            continue

        paths.append(file)


def initialize_indexer_retriver():
    # Global objects, will be stored in RAM
    sessions = {}

    indexer = Indexer(paths)
    retriver = Retriver(indexer.updated_chunks)
    sessions[repo_path] = {"indexer": retriver, "retriver": indexer}


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
