"""Pure-Python learners (no numpy, so they run on any serverless runtime).

* LogisticModel: L2-regularised logistic regression on sparse features, trained by SGD with sample weights.
* NaiveBayes: multinomial naive Bayes over word tokens, for job-type classification.
* evaluate(): k-fold cross-validated accuracy and ROC AUC, so the UI can show how good a model really is.
"""

import math
import random
import re

STOP = {"and", "the", "for", "with", "you", "our", "are", "will", "this", "that", "from", "have", "your", "who", "all", "any",
        "can", "has", "not", "but", "its", "per", "via", "etc", "into", "out", "job", "role", "team", "work"}


def tokens(text: str, limit: int = 4000) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9+#.]{1,30}", (text or "")[:limit].lower()) if w not in STOP and len(w) > 2]


def sigmoid(z: float) -> float:
    if z < -35:
        return 0.0
    if z > 35:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


class LogisticModel:
    def __init__(self, weights: dict[str, float] | None = None):
        self.w: dict[str, float] = dict(weights or {})

    def predict(self, x: dict[str, float]) -> float:
        return sigmoid(sum(self.w.get(k, 0.0) * v for k, v in x.items()))

    def fit(self, X: list[dict[str, float]], y: list[int], sw: list[float] | None = None, *, epochs: int = 40,
            lr: float = 0.15, l2: float = 0.002, seed: int = 7) -> "LogisticModel":
        sw = sw or [1.0] * len(X)
        idx = list(range(len(X)))
        rng = random.Random(seed)  # noqa: S311 - shuffling training data, not security
        # balance classes so a user who mostly dislikes jobs still gets a useful ranker
        pos = sum(w for w, t in zip(sw, y, strict=True) if t) or 1.0
        neg = sum(w for w, t in zip(sw, y, strict=True) if not t) or 1.0
        bal = {1: (pos + neg) / (2 * pos), 0: (pos + neg) / (2 * neg)}
        for ep in range(epochs):
            rng.shuffle(idx)
            step = lr / (1 + ep * 0.05)
            for i in idx:
                x, t = X[i], y[i]
                g = (self.predict(x) - t) * sw[i] * bal[t]
                for k, v in x.items():
                    self.w[k] = self.w.get(k, 0.0) * (1 - step * l2) - step * g * v
        self.w = {k: round(v, 5) for k, v in self.w.items() if abs(v) > 1e-4}
        return self

    def top(self, n: int = 8) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
        items = sorted(((k, v) for k, v in self.w.items() if k != "bias"), key=lambda kv: kv[1])
        return [kv for kv in reversed(items[-n:]) if kv[1] > 0], [kv for kv in items[:n] if kv[1] < 0]


class NaiveBayes:
    def __init__(self, state: dict | None = None):
        s = state or {}
        self.counts: dict[str, dict[str, int]] = s.get("counts", {})
        self.docs: dict[str, int] = s.get("docs", {})

    def fit(self, texts: list[str], labels: list[str]) -> "NaiveBayes":
        for text, lab in zip(texts, labels, strict=True):
            self.docs[lab] = self.docs.get(lab, 0) + 1
            bag = self.counts.setdefault(lab, {})
            for w in tokens(text):
                bag[w] = bag.get(w, 0) + 1
        return self

    def predict(self, text: str) -> tuple[str | None, float]:
        if not self.docs:
            return None, 0.0
        vocab = {w for bag in self.counts.values() for w in bag}
        total = sum(self.docs.values())
        words = tokens(text)
        logp = {}
        for lab, n in self.docs.items():
            bag = self.counts.get(lab, {})
            size = sum(bag.values()) + len(vocab) + 1
            logp[lab] = math.log(n / total) + sum(math.log((bag.get(w, 0) + 1) / size) for w in words)
        best = max(logp, key=logp.get)
        m = max(logp.values())
        z = sum(math.exp(v - m) for v in logp.values())
        return best, 1.0 / z

    def state(self) -> dict:
        return {"counts": self.counts, "docs": self.docs}


def auc(scores: list[float], y: list[int]) -> float | None:
    pos = [s for s, t in zip(scores, y, strict=True) if t]
    neg = [s for s, t in zip(scores, y, strict=True) if not t]
    if not pos or not neg:
        return None
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 3)


def evaluate(X: list[dict[str, float]], y: list[int], sw: list[float], k: int = 5) -> dict:
    """k-fold cross-validation (leave-one-out style when there is little data)."""
    n = len(X)
    k = max(2, min(k, n))
    order = list(range(n))
    random.Random(11).shuffle(order)  # noqa: S311
    preds = [0.0] * n
    for f in range(k):
        test = set(order[f::k])
        tr = [i for i in range(n) if i not in test]
        if len({y[i] for i in tr}) < 2:
            continue
        m = LogisticModel().fit([X[i] for i in tr], [y[i] for i in tr], [sw[i] for i in tr], epochs=25)
        for i in test:
            preds[i] = m.predict(X[i])
    acc = sum((p >= 0.5) == bool(t) for p, t in zip(preds, y, strict=True)) / n
    return {"accuracy": round(acc, 3), "auc": auc(preds, y), "folds": k}
