# Intensive Weight Optimization Plan

This document outlines approaches for finding theoretically optimal fuzzy matching weights, assuming unlimited computing power.

## Current State

**Best weights found via grid search (0.05 increments, 110 configs, ~26 min on Luis' laptop with 24 cores):**

```python
{"title": 0.25, "author": 0.25, "date": 0.2, "bonus": 0.3}
```

| Metric | Value |
|--------|-------|
| P@1 | 96.72% |
| R@5 | 98.09% |
| MRR | 0.9738 |

**Benchmark timing:** ~12 seconds per weight configuration evaluation (5,000 cases against 4,140 bibliography items)

---

## Approach 1: Fine-Grained Grid Search (0.01 increments)

### Description
Exhaustive search over weight space with 1% granularity.

### Configuration Space
```
title:  0.10, 0.11, 0.12, ..., 0.60  (51 values)
author: 0.10, 0.11, 0.12, ..., 0.50  (41 values)
bonus:  0.05, 0.06, 0.07, ..., 0.40  (36 values)
date:   1.0 - title - author - bonus (derived, must be ≥ 0)
```

### Computational Cost
| Metric | Value |
|--------|-------|
| Total combinations | ~75,000 (with constraints) |
| Time per evaluation | 12 seconds |
| **Single-threaded runtime** | **250 hours (~10 days)** |
| With 8 cores | ~31 hours |
| With 24 cores | ~10 hours |
| With 64 cores | ~4 hours |

### Expected Improvement
- Likely 0.1-0.3% improvement over current
- Diminishing returns expected

### Implementation
```python
# Parallelizable with joblib or multiprocessing
from joblib import Parallel, delayed

def evaluate_weights(title, author, bonus, ground_truth, index):
    date = round(1.0 - title - author - bonus, 2)
    if date < 0 or date > 0.3:
        return None
    weights = {"title": title, "author": author, "date": date, "bonus": bonus}
    results = run_benchmark(ground_truth, index, weights=weights, top_n=5)
    return (weights, compute_precision_at_1(results))

results = Parallel(n_jobs=-1)(
    delayed(evaluate_weights)(t, a, b, ground_truth, index)
    for t in np.arange(0.10, 0.61, 0.01)
    for a in np.arange(0.10, 0.51, 0.01)
    for b in np.arange(0.05, 0.41, 0.01)
)
```

---

## Approach 2: Ultra-Fine Grid Search (0.005 increments)

### Description
Maximum granularity grid search for theoretical completeness.

### Computational Cost
| Metric | Value |
|--------|-------|
| Total combinations | ~600,000 |
| **Single-threaded runtime** | **83 days** |
| With 24 cores | ~3.5 days |
| With 100 cores | ~20 hours |
| With 500 cores (cloud) | ~4 hours |

### Expected Improvement
- Marginal (0.01-0.05%) over 0.01 grid
- **Not recommended** - diminishing returns

---

## Approach 3: Bayesian Optimization (Recommended)

### Description
Uses probabilistic surrogate models (Gaussian Processes) to intelligently explore the weight space. Balances exploration vs exploitation.

### Libraries
- **Optuna** (recommended) - easy to use, efficient
- **scikit-optimize** - Gaussian Process based
- **Hyperopt** - Tree-structured Parzen Estimator

### Computational Cost
| Metric | Value |
|--------|-------|
| Evaluations needed | 200-500 (typically) |
| **Runtime** | **40 min - 2 hours** |
| Parallelizable | Yes (with Optuna) |

### Expected Improvement
- Often matches or exceeds fine grid search
- Much more efficient

### Implementation
```python
import optuna

def objective(trial):
    title = trial.suggest_float("title", 0.1, 0.6)
    author = trial.suggest_float("author", 0.1, 0.5)
    bonus = trial.suggest_float("bonus", 0.05, 0.4)
    date = 1.0 - title - author - bonus

    if date < 0 or date > 0.3:
        return 0.0  # Invalid configuration

    weights = {"title": title, "author": author, "date": date, "bonus": bonus}
    results = run_benchmark(ground_truth, index, weights=weights, top_n=5)
    return compute_precision_at_1(results)

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=300, n_jobs=8)

print(f"Best P@1: {study.best_value:.4f}")
print(f"Best weights: {study.best_params}")
```

---

## Approach 4: CMA-ES (Covariance Matrix Adaptation Evolution Strategy)

### Description
State-of-the-art evolutionary algorithm for continuous optimization. Adapts search distribution based on successful samples.

### Computational Cost
| Metric | Value |
|--------|-------|
| Evaluations needed | 500-2000 |
| **Runtime** | **2-7 hours** |
| Parallelizable | Yes (population-based) |

### Expected Improvement
- Often finds global optimum for smooth landscapes
- Handles constraints naturally

### Implementation
```python
import cma

def objective(x):
    title, author, bonus = x
    date = 1.0 - title - author - bonus
    if date < 0 or date > 0.3 or any(v < 0 for v in x):
        return 1.0  # Penalty for invalid

    weights = {"title": title, "author": author, "date": date, "bonus": bonus}
    results = run_benchmark(ground_truth, index, weights=weights, top_n=5)
    return -compute_precision_at_1(results)  # Minimize negative

x0 = [0.25, 0.25, 0.3]  # Starting point
sigma0 = 0.1  # Initial step size
es = cma.CMAEvolutionStrategy(x0, sigma0, {'bounds': [[0.1, 0.1, 0.05], [0.6, 0.5, 0.4]]})
es.optimize(objective)
```

---

## Approach 5: Multi-Objective Optimization (NSGA-II)

### Description
Optimizes P@1, R@5, and MRR simultaneously. Returns a Pareto front of non-dominated solutions.

### Why Multi-Objective?
- P@1, R@5, MRR may conflict slightly
- User can choose trade-off point
- Reveals relationship between metrics

### Computational Cost
| Metric | Value |
|--------|-------|
| Evaluations needed | 2000-10000 |
| **Runtime** | **7-33 hours** |
| With 24 cores | ~1-2 hours |

### Implementation
```python
import optuna

def objective(trial):
    title = trial.suggest_float("title", 0.1, 0.6)
    author = trial.suggest_float("author", 0.1, 0.5)
    bonus = trial.suggest_float("bonus", 0.05, 0.4)
    date = 1.0 - title - author - bonus

    if date < 0 or date > 0.3:
        return 0.0, 0.0, 0.0

    weights = {"title": title, "author": author, "date": date, "bonus": bonus}
    results = run_benchmark(ground_truth, index, weights=weights, top_n=5)

    p1 = compute_precision_at_1(results)
    r5 = compute_recall_at_k(results, k=5)
    mrr = compute_mrr(results)

    return p1, r5, mrr

study = optuna.create_study(directions=["maximize", "maximize", "maximize"])
study.optimize(objective, n_trials=5000, n_jobs=24)

# Get Pareto front
pareto_trials = [t for t in study.best_trials]
```

---

## Approach 6: K-Fold Cross-Validation

### Description
Split ground truth into K folds, train on K-1, validate on 1. Prevents overfitting to benchmark.

### Why Important
- Current 96.72% may be overfit to PhilStudies benchmark
- Cross-validation gives more robust estimate
- Essential for production weights

### Computational Cost
| Metric | Value |
|--------|-------|
| Multiplier | K (typically 5-10) |
| Combined with Bayesian (300 trials, K=5) | ~3.5 hours |
| Combined with fine grid (75K configs, K=5) | ~52 days single-threaded |

### Implementation
```python
from sklearn.model_selection import KFold

def cross_validate_weights(weights, ground_truth, index, k=5):
    kf = KFold(n_splits=k, shuffle=True, random_state=42)
    scores = []

    for train_idx, val_idx in kf.split(ground_truth):
        val_cases = [ground_truth[i] for i in val_idx]
        results = run_benchmark(val_cases, index, weights=weights, top_n=5)
        scores.append(compute_precision_at_1(results))

    return np.mean(scores), np.std(scores)
```

---

## Approach 7: Ensemble / Bootstrap Confidence Intervals

### Description
Run optimization multiple times with different random seeds, bootstrap samples. Get confidence intervals on optimal weights.

### Computational Cost
| Metric | Value |
|--------|-------|
| Bootstraps | 100-1000 |
| Combined with Bayesian | ~4-40 hours |

### Why Important
- Quantifies uncertainty in optimal weights
- Reveals if optimum is sharp or flat

---

## Summary: Recommended Strategy

### For Maximum Theoretical Accuracy (Unlimited Compute)

1. **Start with Bayesian Optimization** (300 trials, ~1 hour)
   - Get approximate optimum quickly

2. **Fine-tune with fine grid** around Bayesian optimum (0.01 steps, ±0.1 range)
   - ~5,000 configs, ~17 hours

3. **Validate with 10-fold cross-validation**
   - Multiply by 10 → ~170 hours total

4. **Bootstrap confidence intervals** (100 samples)
   - Get uncertainty estimates

**Total: ~200-300 hours of compute** (~8-12 days single machine, ~1 day with 24 cores)

### Quick & Good (Recommended for Most Cases)

1. **Bayesian Optimization with CV** (300 trials, 5-fold)
   - ~6 hours with 8 cores
   - Likely within 0.1% of theoretical optimum

---
