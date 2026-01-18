# Fuzzy Matcher

## Quick Start (CLI)

```bash
# Run fuzzy matching on gateway output (e.g., from BeebeBib, RawText)
.venv/bin/python -m philoch_bib_enhancer.cli.fuzzy_matcher_cli \
  --input data/test-2/dialectica.csv \
  --bibliography data/biblio/biblio-v10-table.ods \
  --output data/test-2/dialectica-merged.csv \
  --top-n 5

# Show help
.venv/bin/python -m philoch_bib_enhancer.cli.fuzzy_matcher_cli --help
```

## Input Format

The CLI accepts CSV/ODS files from gateway output (e.g., `manual_raw_text_to_csv.py`, BeebeBib):
- 60 `FormattedBibItem` columns + `parsing_status`, `message`, `context`
- **Empty bibkeys are allowed** - temporary keys (`temp:2`, `temp:3`, etc.) are assigned automatically

## Output Format

The output CSV contains:
1. **All 63 bibliography columns** (exact order from `ParsedBibItemData`)
2. **Match columns appended at the end**:
   - `match_1_bibkey`, `match_1_score`, `match_1_full_entry`
   - `match_2_bibkey`, `match_2_score`, `match_2_full_entry`
   - ... up to `match_N_bibkey`, `match_N_score`, `match_N_full_entry`
   - `candidates_searched`, `search_time_ms`

The `match_X_full_entry` column contains a plaintext citation for easy review.

## Quick Start (Rust Setup)

```bash
# 1. Build the Rust scorer (first time only, or after Rust code changes)
cd /home/alebg/philosophie-ch/bibliography/bib-sdk/philoch_bib_sdk/rust_scorer
maturin build --release -o ./dist

# 2. Install to your venv
pip install ./dist/rust_scorer-0.1.0-cp313-cp313-manylinux_2_34_x86_64.whl --force-reinstall

# 3. Verify installation
python -c "import rust_scorer; print('OK')"
```

## CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `--input` | `-i` | Input file from gateway output (.csv or .ods) |
| `--bibliography` | `-b` | Bibliography file to match against (.ods) |
| `--output` | `-o` | Output CSV file path (merged format) |
| `--cache-dir` | `-c` | Index cache directory (default: data/cache) |
| `--top-n` | `-n` | Top matches per item (default: 5) |
| `--min-score` | `-m` | Minimum score threshold (default: 0.0) |
| `--force-rebuild` | | Force rebuild index cache |
| `--force-python` | | Use Python scorer instead of Rust |

## Python API

```python
from philoch_bib_sdk.logic.functions.fuzzy_matcher import (
    build_index_cached,
    stage_bibitems_batch,
)

# Load/build index (cached after first run)
index = build_index_cached(bibliography, cache_path=Path("data/cache/index.pkl"))

# Run fuzzy matching (auto-uses Rust if available)
staged = stage_bibitems_batch(subjects, index, top_n=5)

# Force Python fallback if needed
staged = stage_bibitems_batch(subjects, index, top_n=5, use_rust=False)
```

---

## Overview

The fuzzy matcher finds similar BibItems in a large bibliography (~209K items) using:

1. **Blocking indexes** - Reduce search space via DOI, title trigrams, author surnames, year decades, journals
2. **Fuzzy scoring** - Compare candidates using weighted title/author/date/bonus scores
3. **Rust acceleration** - Parallel batch scoring via rayon (12x faster than Python)

## Performance

| Dataset | Python | Rust |
|---------|--------|------|
| 10 subjects vs 209K | 80s | 3s |
| 2,238 subjects (dialectica) | ~5 hours | ~24 min |

## Architecture

```
stage_bibitems_batch(subjects, index)
  │
  ├─ [Rust available] → _find_similar_batch_rust()
  │     └─ rust_scorer.score_batch() ← parallel via rayon
  │
  └─ [Python fallback] → stage_bibitem() per subject
        └─ find_similar_bibitems()
              ├─ _get_candidate_set() ← blocking indexes
              └─ compare_bibitems_detailed() ← fuzzy scoring
```

## Scoring Weights

| Component | Weight | Bonus |
|-----------|--------|-------|
| Title | 0.5 | +100 if >85% match or containment |
| Author | 0.3 | +100 if >85% match |
| Date | 0.1 | 100 (exact) → 0 (>3 years diff) |
| Bonus fields | 0.1 | DOI +100, Journal+Vol+Num +50, Pages +20 |

## Files

- `philoch_bib_enhancer/cli/fuzzy_matcher_cli.py` - CLI entry point
- `philoch_bib_sdk/logic/functions/fuzzy_matcher.py` - Core fuzzy matching logic
- `philoch_bib_sdk/rust_scorer/` - Rust extension (PyO3 + rayon)
- `tests/logic/functions/test_fuzzy_matcher.py` - Tests (21 tests)
