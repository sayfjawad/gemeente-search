"""Embed every chunk in index.sqlite with BGE-M3 (GPU) and write embeddings.npy.

Same shape convention as wilders-search/build_index.py: row i of the
(n_chunks, 1024) fp16 array is the embedding for chunks.id == i (chunk ids
are assigned contiguously by ingest.py, so this holds by construction).
"""
import sqlite3
import time
from pathlib import Path

import numpy as np
import torch

from embedder import DIM, Embedder

BASE = Path(__file__).parent
DB_PATH = BASE / "data" / "index.sqlite"
EMB_PATH = BASE / "data" / "embeddings.npy"

TOKEN_BUDGET = 16384


def main():
    db = sqlite3.connect(DB_PATH)
    rows = db.execute("SELECT id, text FROM chunks ORDER BY id").fetchall()
    db.close()
    n = len(rows)
    assert [r[0] for r in rows] == list(range(n)), "chunk ids must be contiguous 0..n-1"
    texts = [r[1] for r in rows]
    print(f"embedding {n} chunks...", flush=True)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    embedder = Embedder(device=device)
    tok = embedder.tokenizer

    lengths = [len(t) for t in texts]
    order = np.argsort(lengths)
    emb = np.zeros((n, DIM), dtype=np.float16)

    batch_idx: list[int] = []
    batch_max_tok = 0
    done = 0
    t0 = time.time()

    def flush():
        nonlocal batch_idx, batch_max_tok, done
        if not batch_idx:
            return
        vecs = embedder.encode([texts[i] for i in batch_idx]).numpy().astype(np.float16)
        emb[batch_idx] = vecs
        done += len(batch_idx)
        if done % 500 < len(batch_idx):
            rate = done / (time.time() - t0)
            eta = (n - done) / max(rate, 1)
            print(f"  {done}/{n}  {rate:.0f} chunks/s  eta {eta:.0f}s", flush=True)
        batch_idx = []
        batch_max_tok = 0

    for i in order:
        ntok = min(len(tok.encode(texts[i], add_special_tokens=True)), embedder.max_length)
        new_max = max(batch_max_tok, ntok)
        if batch_idx and new_max * (len(batch_idx) + 1) > TOKEN_BUDGET:
            flush()
            new_max = ntok
        batch_idx.append(int(i))
        batch_max_tok = new_max
    flush()

    np.save(EMB_PATH, emb)
    print(f"done in {time.time()-t0:.0f}s -> {EMB_PATH}", flush=True)


if __name__ == "__main__":
    main()
