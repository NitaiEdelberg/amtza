"""Read word vectors from a fastText .bin without loading it into memory.

Used by scripts/build_middle_vectors.py. The Hebrew Common Crawl model
(cc.he.300.bin, 7.2GB) is bigger than a typical dev machine's free RAM, so the
input matrix is memory-mapped and only the rows a word needs are read.

A word's vector is exactly what fastText's get_word_vector returns: the mean of
the word's own row and its character n-gram rows, hashed with fastText's FNV-1a
into the bucket table. That is also what the published .vec files contain, and
it works for words outside the model's vocabulary too.

Get the model from Facebook's own Hugging Face copy (its fbaipublicfiles host has
had an expired certificate since 2026-11):
    https://huggingface.co/facebook/fasttext-he-vectors/resolve/main/model.bin
and check its sha256 against the X-Linked-ETag header Hugging Face serves.
"""
import json, struct, sys
import numpy as np


def read_model(path):
    f = open(path, "rb")
    magic, version = struct.unpack("<ii", f.read(8))
    assert magic == 793712314, magic
    (dim, ws, epoch, min_count, neg, word_ngrams, loss, model, bucket, minn, maxn,
     lr_update) = struct.unpack("<12i", f.read(48))
    (t,) = struct.unpack("<d", f.read(8))
    size, nwords, nlabels = struct.unpack("<3i", f.read(12))
    ntokens, prune_size = struct.unpack("<qq", f.read(16))
    words = []
    # Dictionary entries: NUL-terminated word, int64 count, int8 type.
    for _ in range(size):
        chars = bytearray()
        while True:
            c = f.read(1)
            if c == b"\x00":
                break
            chars += c
        f.read(9)
        words.append(bytes(chars))
    if prune_size > 0:
        f.read(8 * prune_size)
    (quant,) = struct.unpack("<?", f.read(1))
    assert not quant
    m, n = struct.unpack("<qq", f.read(16))
    assert n == dim and m == nwords + bucket, (m, n, nwords, bucket)
    offset = f.tell()
    f.close()
    matrix = np.memmap(path, dtype=np.float32, mode="r", offset=offset, shape=(m, n))
    return dict(words=words, nwords=nwords, bucket=bucket, minn=minn, maxn=maxn, dim=dim,
                matrix=matrix, index={w: i for i, w in enumerate(words)})


def fnv1a(b):
    h = 2166136261
    for byte in b:
        # fastText hashes int8_t(byte) cast to uint32: bytes >= 0x80 sign-extend.
        h ^= (byte - 256 if byte >= 128 else byte) & 0xFFFFFFFF
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def subword_rows(model, word_bytes):
    w = b"<" + word_bytes + b">"
    rows = []
    for i in range(len(w)):
        if (w[i] & 0xC0) == 0x80:
            continue
        j, n, ngram = i, 1, bytearray()
        while j < len(w) and n <= model["maxn"]:
            ngram.append(w[j]); j += 1
            while j < len(w) and (w[j] & 0xC0) == 0x80:
                ngram.append(w[j]); j += 1
            if n >= model["minn"] and not (n == 1 and (i == 0 or j == len(w))):
                rows.append(model["nwords"] + fnv1a(ngram) % model["bucket"])
            n += 1
    return rows


def word_vector(model, word):
    b = word.encode("utf-8")
    rows = subword_rows(model, b)
    idx = model["index"].get(b)
    if idx is not None:
        rows = [idx] + rows
    if not rows:
        return None
    v = np.asarray(model["matrix"][sorted(rows)], dtype=np.float32).mean(axis=0)
    norm = np.linalg.norm(v)
    return v / norm if norm else v
