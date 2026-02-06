use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use rayon::prelude::*;
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap, HashSet};
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

/// Academic review/response prefixes - used as a gate in fuzzy matching.
/// If one title starts with a prefix and the other doesn't, they cannot match.
const ACADEMIC_REVIEW_PREFIXES: &[&str] = &[
    "reply to",
    "comments on",
    "précis of",
    "precis of",
    "review of",
    "critical notice",
    "symposium on",
    "discussion of",
    "response to",
    "a reply to",
    "responses to",
];

/// Check if a title starts with an academic review/response prefix
fn has_academic_prefix(title: &str) -> bool {
    let normalized = title.to_lowercase();
    let trimmed = normalized.trim();
    ACADEMIC_REVIEW_PREFIXES
        .iter()
        .any(|prefix| trimmed.starts_with(prefix))
}

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

    token_sort_ratio_f64_prenormalized(&norm1, &norm2)
}

/// Token sort ratio on already-normalized strings (avoids double normalization)
fn token_sort_ratio_f64_prenormalized(norm1: &str, norm2: &str) -> f64 {
    if norm1.is_empty() || norm2.is_empty() {
        return 0.0;
    }

    let sorted1 = tokenize_and_sort(norm1).join(" ");
    let sorted2 = tokenize_and_sort(norm2).join(" ");

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

/// Score title similarity with bonuses (takes pre-normalized title for subject)
fn score_title_prenorm(norm_subject: &str, title2: &str, weight: f64) -> f64 {
    if norm_subject.is_empty() || title2.is_empty() {
        return 0.0;
    }

    let norm2 = normalize(title2);

    let raw_score = token_sort_ratio_f64_prenormalized(norm_subject, &norm2);

    // Check if one title contains the other (subtitle handling)
    let one_contains_other = norm_subject.contains(&norm2) || norm2.contains(norm_subject);

    // Check for undesired keywords mismatch (no allocation version)
    let has_errata1 = norm_subject.contains("errata");
    let has_errata2 = norm2.contains("errata");
    let has_review1 = norm_subject.contains("review");
    let has_review2 = norm2.contains("review");
    let kw_mismatch = has_errata1 != has_errata2 || has_review1 != has_review2;

    let mut final_score = raw_score;

    // High similarity bonus
    if (raw_score > 85.0 || one_contains_other) && !kw_mismatch {
        final_score += 100.0;
    }

    // Penalty for keyword mismatch
    if kw_mismatch {
        let penalty_count =
            i32::from(has_errata1 != has_errata2) + i32::from(has_review1 != has_review2);
        final_score -= f64::from(penalty_count * 50);
    }

    final_score.max(0.0) * weight
}

/// Score title similarity with bonuses (normalizes both titles)
fn score_title(title1: &str, title2: &str, weight: f64) -> f64 {
    if title1.is_empty() || title2.is_empty() {
        return 0.0;
    }

    let norm1 = normalize(title1);
    score_title_prenorm(&norm1, title2, weight)
}

/// Check if a name part is an initial (e.g., "E." or "E")
fn is_initial(name: &str) -> bool {
    let cleaned = name.trim_end_matches('.');
    cleaned.len() == 1 && cleaned.chars().next().is_some_and(|c| c.is_alphabetic())
}

/// Get the uppercase initial letter from a name part
fn get_initial_letter(name: &str) -> Option<char> {
    name.trim_end_matches('.')
        .chars()
        .next()
        .map(|c| c.to_ascii_uppercase())
}

/// Extract given name parts and surname from an author string
/// Returns (given_names, surname)
fn extract_name_parts(author: &str) -> (Vec<&str>, &str) {
    let parts: Vec<&str> = author.split_whitespace().collect();
    if parts.len() < 2 {
        return (vec![], parts.first().copied().unwrap_or(""));
    }
    // Assume last part is surname, rest are given names
    let surname = parts.last().unwrap();
    let given = parts[..parts.len() - 1].to_vec();
    (given, surname)
}

/// Check if one author string uses initials that match the other's full names.
/// Handles cases like "E. M. Adams" vs "Ernest M. Adams" or "J. Smith" vs "John Smith".
fn check_initials_match(author1: &str, author2: &str) -> bool {
    let (given1, surname1) = extract_name_parts(author1);
    let (given2, surname2) = extract_name_parts(author2);

    // Quick surname check - must start with same letter
    let s1_initial = get_initial_letter(surname1);
    let s2_initial = get_initial_letter(surname2);
    if s1_initial != s2_initial {
        return false;
    }

    // Fuzzy surname check (only call once, not in loop)
    let surname_score = token_sort_ratio_f64(&surname1.to_lowercase(), &surname2.to_lowercase());
    if surname_score < 80.0 {
        return false;
    }

    // Count initials in each given name list
    let initials_count1 = given1.iter().filter(|g| is_initial(g)).count();
    let initials_count2 = given2.iter().filter(|g| is_initial(g)).count();

    // If same number of initials (including both zero), no special handling needed
    // We want cases where one uses more initials than the other
    if initials_count1 == initials_count2 {
        return false;
    }

    // Determine which has more initials (the "initial form") vs fewer (the "full form")
    let (initial_given, full_given) = if initials_count1 > initials_count2 {
        (&given1, &given2)
    } else {
        (&given2, &given1)
    };

    // Check if initials in the initial form match first letters of full form
    let mut matches = 0;
    for (i, name) in initial_given.iter().enumerate() {
        if i >= full_given.len() {
            break;
        }
        // Compare first letters regardless of whether it's an initial or full name
        let letter1 = get_initial_letter(name);
        let letter2 = get_initial_letter(full_given[i]);
        if letter1 == letter2 {
            matches += 1;
        }
    }

    // Require at least one match, and allow at most one mismatch
    let min_names = initial_given.len().min(full_given.len());
    matches > 0 && matches >= min_names.saturating_sub(1)
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
    } else {
        // Check for initial matching (e.g., "E. M. Adams" vs "Ernest M. Adams")
        if check_initials_match(author1, author2) {
            final_score += 50.0;
        }
    }

    final_score * weight
}

/// Score date similarity with wider tolerance for CrossRef date discrepancies
/// (online-early vs issue date can differ by several years)
fn score_date(year1: Option<i32>, year2: Option<i32>, weight: f64) -> f64 {
    match (year1, year2) {
        (Some(y1), Some(y2)) => {
            let diff = y1.abs_diff(y2);
            let score = match diff {
                0 => 100.0,
                1 => 95.0,
                2 => 90.0,
                3 => 85.0,
                4 => 75.0,
                5 => 65.0,
                _ if y1 / 10 == y2 / 10 => 40.0, // Same decade
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

/// Score bonus fields with precomputed subject data (avoids repeated normalization)
fn score_bonus_precomputed(
    subject: &PrecomputedSubject,
    candidate: &BibItemData,
    weight: f64,
) -> f64 {
    let mut bonus = 0.0;

    // DOI exact match (highest confidence)
    if let (Some(ref doi1), Some(ref doi2)) = (&subject.data.doi, &candidate.doi) {
        if !doi1.is_empty() && doi1 == doi2 {
            bonus += 100.0;
        }
    }

    // Journal + Volume + Number match (use precomputed normalized journal)
    if let (Some(ref norm_j1), Some(ref j2)) = (&subject.normalized_journal, &candidate.journal) {
        let norm_j2 = normalize(j2);
        if !norm_j1.is_empty() && norm_j1 == &norm_j2 {
            let vol_match = match (&subject.data.volume, &candidate.volume) {
                (Some(v1), Some(v2)) => !v1.is_empty() && v1 == v2,
                _ => false,
            };
            let num_match = match (&subject.data.number, &candidate.number) {
                (Some(n1), Some(n2)) => !n1.is_empty() && n1 == n2,
                _ => false,
            };
            if vol_match && num_match {
                bonus += 50.0;
            }
        }
    }

    // Pages match
    if let (Some(ref p1), Some(ref p2)) = (&subject.data.pages, &candidate.pages) {
        if !p1.is_empty() && p1 == p2 {
            bonus += 20.0;
        }
    }

    // Publisher match (use precomputed normalized publisher)
    if let (Some(ref norm_pub1), Some(ref pub2)) =
        (&subject.normalized_publisher, &candidate.publisher)
    {
        if !norm_pub1.is_empty() && !pub2.is_empty() {
            let norm_pub2 = normalize(pub2);
            let pub_score = token_sort_ratio_f64_prenormalized(norm_pub1, &norm_pub2);
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

/// Precomputed data for a subject to avoid recomputation per candidate
struct PrecomputedSubject<'a> {
    data: &'a BibItemData,
    has_academic_prefix: bool,
    normalized_title: String,
    normalized_journal: Option<String>,
    normalized_publisher: Option<String>,
}

impl<'a> PrecomputedSubject<'a> {
    fn new(data: &'a BibItemData) -> Self {
        Self {
            data,
            has_academic_prefix: has_academic_prefix(&data.title),
            normalized_title: normalize(&data.title),
            normalized_journal: data.journal.as_ref().map(|j| normalize(j)),
            normalized_publisher: data.publisher.as_ref().map(|p| normalize(p)),
        }
    }
}

/// Score a single candidate against a subject with configurable weights
fn score_candidate(
    subject: &BibItemData,
    candidate: &BibItemData,
    weights: &Weights,
) -> MatchResult {
    // Academic prefix gate: if one title has prefix and other doesn't, automatic non-match
    let subject_has_prefix = has_academic_prefix(&subject.title);
    let candidate_has_prefix = has_academic_prefix(&candidate.title);
    if subject_has_prefix != candidate_has_prefix {
        return MatchResult {
            candidate_index: candidate.index,
            total_score: 0.0,
            title_score: 0.0,
            author_score: 0.0,
            date_score: 0.0,
            bonus_score: 0.0,
        };
    }

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

/// Score a single candidate against precomputed subject data (optimized)
fn score_candidate_precomputed(
    subject: &PrecomputedSubject,
    candidate: &BibItemData,
    weights: &Weights,
) -> MatchResult {
    // Academic prefix gate using precomputed subject prefix
    let candidate_has_prefix = has_academic_prefix(&candidate.title);
    if subject.has_academic_prefix != candidate_has_prefix {
        return MatchResult {
            candidate_index: candidate.index,
            total_score: 0.0,
            title_score: 0.0,
            author_score: 0.0,
            date_score: 0.0,
            bonus_score: 0.0,
        };
    }

    // Use precomputed normalized title
    let title_score =
        score_title_prenorm(&subject.normalized_title, &candidate.title, weights.title);
    let author_score = score_author(&subject.data.author, &candidate.author, weights.author);
    let date_score = score_date(subject.data.year, candidate.year, weights.date);
    let bonus_score = score_bonus_precomputed(subject, candidate, weights.bonus);

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

/// Blocking index data passed from Python for efficient candidate filtering
#[derive(Debug, FromPyObject)]
struct BlockingIndexData {
    #[pyo3(item)]
    doi_index: HashMap<String, usize>,
    #[pyo3(item)]
    trigram_index: HashMap<String, Vec<usize>>,
    #[pyo3(item)]
    surname_index: HashMap<String, Vec<usize>>,
    #[pyo3(item)]
    decade_index: HashMap<i32, Vec<usize>>,
}

/// Get candidate indices for a subject using the blocking index
fn get_candidate_indices(
    subject: &BibItemData,
    index: &BlockingIndexData,
    num_candidates: usize,
) -> Vec<usize> {
    // DOI exact match - return immediately
    if let Some(ref doi) = subject.doi {
        if !doi.is_empty() {
            if let Some(&idx) = index.doi_index.get(doi) {
                return vec![idx];
            }
        }
    }

    let mut indices: HashSet<usize> = HashSet::new();

    // Title trigrams
    let trigrams = extract_trigrams(&subject.title);
    for trigram in trigrams {
        if let Some(idxs) = index.trigram_index.get(&trigram) {
            indices.extend(idxs);
        }
    }

    // Author surnames - check if any indexed surname appears in the author string
    let author_lower = subject.author.to_lowercase();
    for (surname, idxs) in &index.surname_index {
        if author_lower.contains(surname) {
            indices.extend(idxs);
        }
    }

    // Year decades (±5 decades = ±50 years)
    if let Some(year) = subject.year {
        let subject_decade = (year / 10) * 10;
        for offset in -5..=5 {
            let decade = subject_decade + (offset * 10);
            if let Some(idxs) = index.decade_index.get(&decade) {
                indices.extend(idxs);
            }
        }
    }

    // Fallback to all if no candidates found
    if indices.is_empty() {
        return (0..num_candidates).collect();
    }

    indices.into_iter().collect()
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

/// Find top matches using precomputed subject and filtered candidate indices
fn find_top_matches_indexed(
    subject: &PrecomputedSubject,
    candidates: &[BibItemData],
    candidate_indices: &[usize],
    doi_map: &HashMap<&str, usize>,
    top_n: usize,
    min_score: f64,
    weights: &Weights,
) -> (Vec<MatchResult>, usize) {
    // Quick DOI check using prebuilt map (O(1) instead of O(n))
    if let Some(ref subject_doi) = subject.data.doi {
        if !subject_doi.is_empty() {
            if let Some(&cand_idx) = doi_map.get(subject_doi.as_str()) {
                let result = score_candidate_precomputed(subject, &candidates[cand_idx], weights);
                return (vec![result], 1);
            }
        }
    }

    // Score only the filtered candidates
    let mut heap: BinaryHeap<MatchResult> = BinaryHeap::new();

    for &cand_idx in candidate_indices {
        if cand_idx < candidates.len() {
            let result = score_candidate_precomputed(subject, &candidates[cand_idx], weights);
            if result.total_score >= min_score {
                heap.push(result);
            }
        }
    }

    // Extract top N
    let searched = candidate_indices.len();
    let mut results: Vec<MatchResult> = Vec::with_capacity(top_n.min(heap.len()));
    for _ in 0..top_n {
        if let Some(result) = heap.pop() {
            results.push(result);
        } else {
            break;
        }
    }

    (results, searched)
}

/// Batch score with blocking index - filters candidates per subject for massive speedup.
/// This is the primary entry point for fuzzy matching.
#[pyfunction]
fn score_batch_indexed(
    subjects: Vec<BibItemData>,
    candidates: Vec<BibItemData>,
    index: BlockingIndexData,
    top_n: usize,
    min_score: f64,
    weights: Weights,
) -> Vec<SubjectMatchResult> {
    let num_candidates = candidates.len();

    // Build DOI map once for O(1) lookups
    let doi_map: HashMap<&str, usize> = candidates
        .iter()
        .filter_map(|c| {
            c.doi
                .as_ref()
                .filter(|d| !d.is_empty())
                .map(|d| (d.as_str(), c.index))
        })
        .collect();

    subjects
        .par_iter()
        .enumerate()
        .map(|(idx, subject)| {
            // Precompute subject data once
            let precomputed = PrecomputedSubject::new(subject);

            // Get filtered candidate indices from blocking index
            let candidate_indices = get_candidate_indices(subject, &index, num_candidates);

            // Score only filtered candidates
            let (matches, searched) = find_top_matches_indexed(
                &precomputed,
                &candidates,
                &candidate_indices,
                &doi_map,
                top_n,
                min_score,
                &weights,
            );

            SubjectMatchResult {
                subject_index: idx,
                matches,
                candidates_searched: searched,
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
    m.add_function(wrap_pyfunction!(score_batch_indexed, m)?)?;
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
        // ±1 year = 95 (updated for wider tolerance)
        let score = score_date(Some(2020), Some(2021), 1.0);
        assert!((score - 95.0).abs() < 0.001);
    }

    #[test]
    fn test_score_date_wider_tolerance() {
        // ±2 = 90, ±3 = 85, ±4 = 75, ±5 = 65
        assert!((score_date(Some(2020), Some(2022), 1.0) - 90.0).abs() < 0.001);
        assert!((score_date(Some(2020), Some(2023), 1.0) - 85.0).abs() < 0.001);
        assert!((score_date(Some(2020), Some(2024), 1.0) - 75.0).abs() < 0.001);
        assert!((score_date(Some(2020), Some(2025), 1.0) - 65.0).abs() < 0.001);
    }

    #[test]
    fn test_score_date_same_decade() {
        // > 5 years but same decade = 40
        let score = score_date(Some(2020), Some(2028), 1.0);
        assert!((score - 40.0).abs() < 0.001);
    }

    // Academic prefix gate tests
    #[test]
    fn test_has_academic_prefix() {
        assert!(has_academic_prefix("Reply to Smith on Knowledge"));
        assert!(has_academic_prefix("reply to smith")); // case insensitive
        assert!(has_academic_prefix("Comments on the Paper"));
        assert!(has_academic_prefix("Review of Recent Work"));
        assert!(!has_academic_prefix("On the Nature of Knowledge"));
        assert!(!has_academic_prefix("Knowledge and Belief"));
    }

    // Author initials matching tests
    #[test]
    fn test_is_initial() {
        assert!(is_initial("E."));
        assert!(is_initial("E"));
        assert!(!is_initial("Ernest"));
        assert!(!is_initial(""));
    }

    #[test]
    fn test_get_initial_letter() {
        assert_eq!(get_initial_letter("E."), Some('E'));
        assert_eq!(get_initial_letter("Ernest"), Some('E'));
        assert_eq!(get_initial_letter("e."), Some('E')); // uppercase
    }

    #[test]
    fn test_check_initials_match() {
        // "E. M. Adams" vs "Ernest M. Adams" should match
        assert!(check_initials_match("E. M. Adams", "Ernest M. Adams"));
        assert!(check_initials_match("J. Smith", "John Smith"));
        // Different surnames should not match
        assert!(!check_initials_match("E. Adams", "Ernest Jones"));
        // Both full names should not trigger (handled by fuzzy)
        assert!(!check_initials_match("Ernest Adams", "Ernest Adams"));
        // Both initials should not trigger
        assert!(!check_initials_match("E. Adams", "E. Adams"));
    }

    #[test]
    fn test_score_author_with_initials() {
        // With initials matching, should get +50 bonus even if fuzzy is < 85
        let score_with_initials = score_author("E. M. Adams", "Ernest M. Adams", 1.0);
        let score_without_match = score_author("E. M. Adams", "John Smith", 1.0);
        assert!(score_with_initials > score_without_match);
        // The initials bonus is +50
        assert!(score_with_initials >= 50.0);
    }
}
