from rank_bm25 import BM25Okapi
import faiss
from sentence_transformers import SentenceTransformer
import numpy as np


class Retriver:
    def __init__(self, chunks: list, dim: int = 384, k: int = 60):
        self.k = k
        self.bm25 = None
        self.bm25_corpus = []
        base_index = faiss.IndexFlatL2(dim)
        self.faiss = faiss.IndexIDMap(base_index)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.chunk_id_mapping = {}
        self.faiss_add_chunks(chunks)
        self.bm25_add_chunks(chunks)

    def bm25_add_chunks(self, chunks: list):
        self.bm25_corpus.extend(chunks)
        for chunk in chunks:
            self.chunk_id_mapping[chunk["id"]] = chunk
        self.bm25 = BM25Okapi([c["source"].split() for c in self.bm25_corpus])

    def bm25_remove_chunks(self, paths: list):
        for path in paths:
            self.bm25_corpus = [c for c in self.bm25_corpus if c["file"] != path]
            if self.bm25_corpus:
                self.bm25 = BM25Okapi([c["source"].split() for c in self.bm25_corpus])

    def faiss_add_chunks(self, chunks: list, removed_chunks: list = []):
        remove_ids = [chunk["id"] for chunk in removed_chunks]
        updated_ids = []
        new_chunks = []

        for chunk in chunks:
            text = f"""
                type: {chunk.get("type")}
                file: {chunk.get("file")}
                start_line: {chunk.get("start_line")}
                end_line: {chunk.get("end_line")}
                source: {chunk.get("source")}
                name: {chunk.get("name")}
                sub_functions: {chunk.get("sub_functions")}
                doc_string: {chunk.get("doc_string")}
                """

            self.chunk_id_mapping[chunk["id"]] = chunk
            updated_ids.append(chunk["id"])
            emb = self.model.encode(text)
            new_chunks.append(emb)

        if remove_ids:
            self.faiss.remove_ids(np.array(remove_ids, dtype=np.int64))

        if updated_ids:
            self.faiss.add_with_ids(
                np.array(new_chunks), np.array(updated_ids, dtype=np.int64)
            )

    def bm25_retriver(self, query: str, n: int):
        return self.bm25.get_top_n(query.split(), self.bm25_corpus, n)

    def faiss_retriver(self, query: str, updated_chunks: list, n: int):
        if updated_chunks:
            self.faiss_add_chunks(updated_chunks)

        emb_query = self.model.encode(query)
        scores, indexs = self.faiss.search(emb_query.reshape(1, -1), n)
        docs = []

        for i in indexs[0]:
            if i != -1:
                docs.append(self.chunk_id_mapping[i])

        return docs

    def rrf(self, bm25, faiss):
        scores = {}

        for rank, doc in enumerate(bm25):
            score = 1 / (self.k + rank)
            scores[doc["id"]] = scores.get(doc["id"], 0) + score

        for rank, doc in enumerate(faiss):
            score = 1 / (self.k + rank)
            scores[doc["id"]] = scores.get(doc["id"], 0) + score

        reranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        docs = [self.chunk_id_mapping[id] for id, score in reranked]
        return docs

    def retrive(self, query: str, updated_chunks: list = None, n: int = 10):
        bm25_top_n = self.bm25_retriver(query, n)
        faiss_top_n = self.faiss_retriver(query, updated_chunks or [], n)
        rrf = self.rrf(bm25_top_n, faiss_top_n)

        return rrf
