use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use rayon::prelude::*;
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashSet};
use strsim::jaro_winkler;

/// Input data for a single bibliographic item
#[derive(Debug, FromPyObject)]
struct ItemData {
    #[pyo3(item)]
    item_index: usize,
    #[pyo3(item)]
    doi: Option<String>,
    #[pyo3(item)]
    title: String,
    #[pyo3(item)]
    author_surnames: Vec<String>,
    #[pyo3(item)]
    year: Option<i32>,
    #[pyo3(item)]
    journal_name: Option<String>,
}

/// Output index data structure
#[pyclass]
struct IndexData {
    #[pyo3(get)]
    doi_to_index: Py<PyDict>,
    #[pyo3(get)]
    trigram_to_indices: Py<PyDict>,
    #[pyo3(get)]
    surname_to_indices: Py<PyDict>,
    #[pyo3(get)]
    decade_to_indices: Py<PyDict>,
    #[pyo3(get)]
    journal_to_indices: Py<PyDict>,
}

/// Extract trigrams from text
fn extract_trigrams(text: &str) -> HashSet<String> {
    let normalized = text.to_lowercase();
    let chars: Vec<char> = normalized.chars().collect();

    if chars.len() < 3 {
        return HashSet::new();
    }

    let mut trigrams = HashSet::new();
    for i in 0..=chars.len() - 3 {
        let trigram: String = chars[i..i + 3].iter().collect();
        trigrams.insert(trigram);
    }

    trigrams
}

/// Calculate decade from year
fn get_decade(year: Option<i32>) -> Option<i32> {
    year.map(|y| (y / 10) * 10)
}

/// Build index for fuzzy matching
#[pyfunction]
fn build_index_rust(py: Python, items_data: Vec<ItemData>) -> PyResult<IndexData> {
    use ahash::AHashMap;

    // Pre-allocate with capacity hints
    let capacity = items_data.len();
    let mut doi_map: AHashMap<String, usize> = AHashMap::with_capacity(capacity);
    let mut trigram_map: AHashMap<String, Vec<usize>> = AHashMap::new();
    let mut surname_map: AHashMap<String, Vec<usize>> = AHashMap::new();
    let mut decade_map: AHashMap<Option<i32>, Vec<usize>> = AHashMap::new();
    let mut journal_map: AHashMap<String, Vec<usize>> = AHashMap::new();

    // Single pass over all items
    for item in items_data {
        let idx = item.item_index;

        // DOI index
        if let Some(doi) = item.doi {
            doi_map.insert(doi, idx);
        }

        // Title trigram index
        let trigrams = extract_trigrams(&item.title);
        for trigram in trigrams {
            trigram_map.entry(trigram).or_default().push(idx);
        }

        // Author surname index
        for surname in item.author_surnames {
            let normalized = surname.to_lowercase().trim().to_string();
            if !normalized.is_empty() {
                surname_map.entry(normalized).or_default().push(idx);
            }
        }

        // Year decade index
        let decade = get_decade(item.year);
        decade_map.entry(decade).or_default().push(idx);

        // Journal index
        if let Some(journal) = item.journal_name {
            let normalized = journal.to_lowercase().trim().to_string();
            if !normalized.is_empty() {
                journal_map.entry(normalized).or_default().push(idx);
            }
        }
    }

    // Convert to Python dicts
    let doi_dict = PyDict::new(py);
    for (k, v) in doi_map {
        doi_dict.set_item(k, v)?;
    }

    let trigram_dict = PyDict::new(py);
    for (k, v) in trigram_map {
        let py_list = PyList::new(py, &v)?;
        trigram_dict.set_item(k, py_list)?;
    }

    let surname_dict = PyDict::new(py);
    for (k, v) in surname_map {
        let py_list = PyList::new(py, &v)?;
        surname_dict.set_item(k, py_list)?;
    }

    let decade_dict = PyDict::new(py);
    for (k, v) in decade_map {
        let py_list = PyList::new(py, &v)?;
        decade_dict.set_item(k, py_list)?;
    }

    let journal_dict = PyDict::new(py);
    for (k, v) in journal_map {
        let py_list = PyList::new(py, &v)?;
        journal_dict.set_item(k, py_list)?;
    }

    Ok(IndexData {
        doi_to_index: doi_dict.into(),
        trigram_to_indices: trigram_dict.into(),
        surname_to_indices: surname_dict.into(),
        decade_to_indices: decade_dict.into(),
        journal_to_indices: journal_dict.into(),
    })
}

// === SCORER FUNCTIONALITY (merged from rust_scorer) ===

/// Normalize text: lowercase and collapse whitespace
fn normalize(s: &str) -> String {
    s.to_lowercase()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

/// Tokenize and sort tokens alphabetically
fn tokenize_and_sort(s: &str) -> Vec<&str> {
    let mut tokens: Vec<&str> = s.split_whitespace().collect();
    tokens.sort_unstable();
    tokens
}

/// Internal token sort ratio returning f64 (0.0-100.0)
fn token_sort_ratio_f64(s1: &str, s2: &str) -> f64 {
    if s1.is_empty() || s2.is_empty() {
        return 0.0;
    }

    let norm1 = normalize(s1);
    let norm2 = normalize(s2);

    let sorted1 = tokenize_and_sort(&norm1).join(" ");
    let sorted2 = tokenize_and_sort(&norm2).join(" ");

    // Jaro-Winkler returns 0.0-1.0, scale to 0-100
    jaro_winkler(&sorted1, &sorted2) * 100.0
}

/// Token sort ratio for Python: returns float 0.0-100.0
#[pyfunction]
fn token_sort_ratio(s1: &str, s2: &str) -> f64 {
    token_sort_ratio_f64(s1, s2)
}

/// Input data for a single BibItem (for scoring)
#[derive(Clone, Debug, FromPyObject)]
#[pyo3(from_item_all)]
struct BibItemData {
    index: usize,
    title: String,
    author: String,
    year: Option<i32>,
    doi: Option<String>,
    journal: Option<String>,
    volume: Option<String>,
    number: Option<String>,
    pages: Option<String>,
    publisher: Option<String>,
}

/// Result of scoring a candidate against a subject
#[derive(Clone, Debug, IntoPyObject)]
struct MatchResult {
    candidate_index: usize,
    total_score: f64,
    title_score: f64,
    author_score: f64,
    date_score: f64,
    bonus_score: f64,
}

impl PartialEq for MatchResult {
    fn eq(&self, other: &Self) -> bool {
        self.total_score == other.total_score
    }
}

impl Eq for MatchResult {}

impl PartialOrd for MatchResult {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for MatchResult {
    fn cmp(&self, other: &Self) -> Ordering {
        self.total_score
            .partial_cmp(&other.total_score)
            .unwrap_or(Ordering::Equal)
    }
}

/// Score title similarity with bonuses
fn score_title(title1: &str, title2: &str, weight: f64) -> f64 {
    if title1.is_empty() || title2.is_empty() {
        return 0.0;
    }

    let norm1 = normalize(title1);
    let norm2 = normalize(title2);

    let raw_score = token_sort_ratio_f64(&norm1, &norm2);

    // Check if one title contains the other (subtitle handling)
    let one_contains_other = norm1.contains(&norm2) || norm2.contains(&norm1);

    // Check for undesired keywords mismatch
    let undesired = ["errata", "review"];
    let has_undesired1: Vec<_> = undesired.iter().filter(|kw| norm1.contains(*kw)).collect();
    let has_undesired2: Vec<_> = undesired.iter().filter(|kw| norm2.contains(*kw)).collect();
    let kw_mismatch = has_undesired1.len() != has_undesired2.len()
        || has_undesired1.iter().any(|kw| !has_undesired2.contains(kw));

    let mut final_score = raw_score;

    // High similarity bonus
    if (raw_score > 85.0 || one_contains_other) && !kw_mismatch {
        final_score += 100.0;
    }

    // Penalty for keyword mismatch
    if kw_mismatch {
        // penalty_count is at most 2 (size of undesired array), safe to multiply directly
        let penalty_count = has_undesired1.len().abs_diff(has_undesired2.len());
        final_score -= (penalty_count * 50) as f64;
    }

    final_score.max(0.0) * weight
}

/// Score author similarity with bonuses
fn score_author(author1: &str, author2: &str, weight: f64) -> f64 {
    if author1.is_empty() || author2.is_empty() {
        return 0.0;
    }

    let raw_score = token_sort_ratio_f64(author1, author2);
    let mut final_score = raw_score;

    if raw_score > 85.0 {
        final_score += 100.0;
    }

    final_score * weight
}

/// Score date similarity
fn score_date(year1: Option<i32>, year2: Option<i32>, weight: f64) -> f64 {
    match (year1, year2) {
        (Some(y1), Some(y2)) => {
            let diff = y1.abs_diff(y2);
            let score = match diff {
                0 => 100.0,
                1..=3 => 100.0 - f64::from(diff) * 10.0,
                _ if y1 / 10 == y2 / 10 => 30.0, // Same decade
                _ => 0.0,
            };
            score * weight
        }
        _ => 0.0,
    }
}

/// Score bonus fields (DOI, journal+vol+num, pages, publisher)
fn score_bonus(subject: &BibItemData, candidate: &BibItemData, weight: f64) -> f64 {
    let mut bonus = 0.0;

    // DOI exact match (highest confidence)
    if let (Some(ref doi1), Some(ref doi2)) = (&subject.doi, &candidate.doi) {
        if !doi1.is_empty() && doi1 == doi2 {
            bonus += 100.0;
        }
    }

    // Journal + Volume + Number match
    if let (Some(ref j1), Some(ref j2)) = (&subject.journal, &candidate.journal) {
        let norm_j1 = normalize(j1);
        let norm_j2 = normalize(j2);
        if !norm_j1.is_empty() && norm_j1 == norm_j2 {
            let vol_match = match (&subject.volume, &candidate.volume) {
                (Some(v1), Some(v2)) => !v1.is_empty() && v1 == v2,
                _ => false,
            };
            let num_match = match (&subject.number, &candidate.number) {
                (Some(n1), Some(n2)) => !n1.is_empty() && n1 == n2,
                _ => false,
            };
            if vol_match && num_match {
                bonus += 50.0;
            }
        }
    }

    // Pages match
    if let (Some(ref p1), Some(ref p2)) = (&subject.pages, &candidate.pages) {
        if !p1.is_empty() && p1 == p2 {
            bonus += 20.0;
        }
    }

    // Publisher match
    if let (Some(ref pub1), Some(ref pub2)) = (&subject.publisher, &candidate.publisher) {
        if !pub1.is_empty() && !pub2.is_empty() {
            let pub_score = token_sort_ratio_f64(pub1, pub2);
            if pub_score > 85.0 {
                bonus += 10.0;
            }
        }
    }

    bonus * weight
}

/// Scoring weights for the four matching components.
/// Mirrors the Python FuzzyMatchWeights TypedDict — passed as a dict from Python.
#[derive(Clone, Copy, Debug, FromPyObject)]
struct Weights {
    #[pyo3(item)]
    title: f64,
    #[pyo3(item)]
    author: f64,
    #[pyo3(item)]
    date: f64,
    #[pyo3(item)]
    bonus: f64,
}

/// Score a single candidate against a subject with configurable weights
fn score_candidate(
    subject: &BibItemData,
    candidate: &BibItemData,
    weights: &Weights,
) -> MatchResult {
    let title_score = score_title(&subject.title, &candidate.title, weights.title);
    let author_score = score_author(&subject.author, &candidate.author, weights.author);
    let date_score = score_date(subject.year, candidate.year, weights.date);
    let bonus_score = score_bonus(subject, candidate, weights.bonus);

    let total_score = title_score + author_score + date_score + bonus_score;

    MatchResult {
        candidate_index: candidate.index,
        total_score,
        title_score,
        author_score,
        date_score,
        bonus_score,
    }
}

/// Find top N matches for a single subject
fn find_top_matches(
    subject: &BibItemData,
    candidates: &[BibItemData],
    top_n: usize,
    min_score: f64,
    weights: &Weights,
) -> Vec<MatchResult> {
    // Quick DOI check first
    if let Some(ref subject_doi) = subject.doi {
        if !subject_doi.is_empty() {
            for candidate in candidates {
                if let Some(ref cand_doi) = candidate.doi {
                    if subject_doi == cand_doi {
                        return vec![score_candidate(subject, candidate, weights)];
                    }
                }
            }
        }
    }

    // Score all candidates and keep top N
    let mut heap: BinaryHeap<MatchResult> = BinaryHeap::new();

    for candidate in candidates {
        let result = score_candidate(subject, candidate, weights);
        if result.total_score >= min_score {
            heap.push(result);
        }
    }

    // Extract top N
    let mut results: Vec<MatchResult> = Vec::with_capacity(top_n.min(heap.len()));
    for _ in 0..top_n {
        if let Some(result) = heap.pop() {
            results.push(result);
        } else {
            break;
        }
    }

    results
}

/// Result for a single subject with its top matches
#[derive(Clone, Debug, IntoPyObject)]
struct SubjectMatchResult {
    subject_index: usize,
    matches: Vec<MatchResult>,
    candidates_searched: usize,
}

/// Batch score multiple subjects against candidates in parallel.
#[pyfunction]
fn score_batch(
    subjects: Vec<BibItemData>,
    candidates: Vec<BibItemData>,
    top_n: usize,
    min_score: f64,
    weights: Weights,
) -> Vec<SubjectMatchResult> {
    let candidates_len = candidates.len();

    subjects
        .par_iter()
        .enumerate()
        .map(|(idx, subject)| {
            let matches = find_top_matches(subject, &candidates, top_n, min_score, &weights);
            SubjectMatchResult {
                subject_index: idx,
                matches,
                candidates_searched: candidates_len,
            }
        })
        .collect()
}

// === END SCORER FUNCTIONALITY ===

/// A simple test function to verify Rust integration works
#[pyfunction]
fn hello_rust() -> PyResult<String> {
    Ok("Hello from Rust!".to_string())
}

/// A Python module implemented in Rust.
#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hello_rust, m)?)?;
    m.add_function(wrap_pyfunction!(build_index_rust, m)?)?;
    m.add_class::<IndexData>()?;
    // Scorer functions (merged from rust_scorer)
    m.add_function(wrap_pyfunction!(token_sort_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(score_batch, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_trigrams() {
        let text = "hello";
        let trigrams = extract_trigrams(text);

        assert_eq!(trigrams.len(), 3);
        assert!(trigrams.contains("hel"));
        assert!(trigrams.contains("ell"));
        assert!(trigrams.contains("llo"));
    }

    #[test]
    fn test_extract_trigrams_short() {
        let text = "hi";
        let trigrams = extract_trigrams(text);
        assert_eq!(trigrams.len(), 0);
    }

    #[test]
    fn test_get_decade() {
        assert_eq!(get_decade(Some(1995)), Some(1990));
        assert_eq!(get_decade(Some(2000)), Some(2000));
        assert_eq!(get_decade(Some(2025)), Some(2020));
        assert_eq!(get_decade(None), None);
    }

    // Scorer tests (merged from rust_scorer)
    #[test]
    fn test_token_sort_ratio_identical() {
        let score = token_sort_ratio("hello world", "hello world");
        assert!((score - 100.0).abs() < 0.001);
    }

    #[test]
    fn test_token_sort_ratio_reordered() {
        let score = token_sort_ratio("hello world", "world hello");
        assert!((score - 100.0).abs() < 0.001);
    }

    #[test]
    fn test_token_sort_ratio_different() {
        let score = token_sort_ratio("hello world", "goodbye moon");
        assert!(score < 50.0);
    }

    #[test]
    fn test_token_sort_ratio_empty() {
        assert!((token_sort_ratio("", "hello") - 0.0).abs() < 0.001);
        assert!((token_sort_ratio("hello", "") - 0.0).abs() < 0.001);
    }

    #[test]
    fn test_score_date_exact() {
        let score = score_date(Some(2020), Some(2020), 1.0);
        assert!((score - 100.0).abs() < 0.001);
    }

    #[test]
    fn test_score_date_close() {
        let score = score_date(Some(2020), Some(2021), 1.0);
        assert!((score - 90.0).abs() < 0.001);
    }

    #[test]
    fn test_score_date_same_decade() {
        let score = score_date(Some(2020), Some(2025), 1.0);
        assert!((score - 30.0).abs() < 0.001);
    }
}
