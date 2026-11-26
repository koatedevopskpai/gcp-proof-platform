# Rail and utilities seed corpus

Nineteen short, synthetic documents used to exercise retrieval. They are written for
this demonstration and are **not operational guidance**: do not use them for real
switching, isolation, inspection or maintenance decisions.

Each line is a JSON object with an `id` and `content`. The ids are stable so the
same queries can be replayed after changing the embedding model.

Load it into a running `rag-api`:

```powershell
python services/rag-api/scripts/ingest_corpus.py --url http://localhost:8010
```

Documents are embedded at ingest time, so the corpus must be re-ingested after any
change to `EMBEDDING_MODE`, `EMBEDDING_DIM` or the embedding model.
