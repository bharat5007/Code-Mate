from rank_bm25 import BM25Okapi
import faiss
from sentence_transformers import SentenceTransformer


class Retriver:
    def __init__(self, chunks, dim: int = 384):
        self.bm25 = BM25Okapi(chunks)
        base_index = faiss.IndexFlatL2(dim)
        self.faiss = faiss.IndexIDMap(base_index)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def retrive(
        self, query: str, chunks: list = [], updated_chunks: list = [], n: int = 10
    ):
        bm25_top_n = self.bm25.get_top_n(query, chunks, n)
        updated_ids = []
        new_chunks = []

        for chunk in updated_chunks:
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

            updated_ids.append(chunk["id"])
            emb = self.model.encode(text)
            new_chunks.append(emb)

        if updated_ids:
            self.faiss.remove_ids(updated_ids)
            self.faiss.add_with_ids(new_chunks, updated_ids)

        emb_query = self.model.encode(query)
        faiss_top_n = self.faiss.search(emb_query, n)

        rrf_fusion = None

        return rrf_fusion
