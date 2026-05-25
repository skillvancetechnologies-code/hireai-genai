# parser_resumes/

G1 drops the 10 evaluation resume PDFs here, one per case in
`../parser.json` (filenames must match the `input` field).

This folder is gitignored — the PDFs contain real PII and must not be
committed. The `.gitkeep` exists only so the empty folder survives a
clean checkout.

If the folder is empty when `run_evals.py` runs, the parser runner
logs a clean skip (accuracy=null) instead of crashing.
