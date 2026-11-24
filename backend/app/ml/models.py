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


def logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def platt_fit(scores: list[float], y: list[int], steps: int = 300) -> tuple[float, float]:
    """Platt scaling: p' = sigmoid(a * logit(p) + b), fitted on out-of-fold scores so confident-but-wrong models are pulled back.
    Returns (1, 0) (identity) when there is too little data or only one class."""
    if len(scores) < 10 or len(set(y)) < 2:
        return 1.0, 0.0
    z = [logit(s) for s in scores]
    a, b = 1.0, 0.0
    for i in range(steps):
        lr = 0.5 / (1 + i * 0.02)
        ga = gb = 0.0
        for zi, t in zip(z, y, strict=True):
            e = sigmoid(a * zi + b) - t
            ga += e * zi
            gb += e
        a -= lr * ga / len(z)
        b -= lr * gb / len(z)
    return round(max(0.05, min(a, 5.0)), 4), round(max(-5.0, min(b, 5.0)), 4)


class LogisticModel:
    def __init__(self, weights: dict[str, float] | None = None, calibration: tuple[float, float] | list[float] | None = None):
        self.w: dict[str, float] = dict(weights or {})
        self.cal: tuple[float, float] = (float(calibration[0]), float(calibration[1])) if calibration else (1.0, 0.0)

    def raw(self, x: dict[str, float]) -> float:
        return sigmoid(sum(self.w.get(k, 0.0) * v for k, v in x.items()))

    def predict(self, x: dict[str, float]) -> float:
        """Calibrated probability (identical to the raw score until a calibration is set)."""
        p = self.raw(x)
        return p if self.cal == (1.0, 0.0) else sigmoid(self.cal[0] * logit(p) + self.cal[1])

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
                g = (self.raw(x) - t) * sw[i] * bal[t]
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
            preds[i] = m.raw(X[i])
    acc = sum((p >= 0.5) == bool(t) for p, t in zip(preds, y, strict=True)) / n
    a, b = platt_fit(preds, y)
    cal = [sigmoid(a * logit(p) + b) for p in preds]
    brier = sum((p - t) ** 2 for p, t in zip(preds, y, strict=True)) / n
    brier_cal = sum((p - t) ** 2 for p, t in zip(cal, y, strict=True)) / n
    return {"accuracy": round(acc, 3), "auc": auc(preds, y), "folds": k, "brier": round(brier, 4), "brier_calibrated": round(brier_cal, 4),
            "calibration": [a, b], "n": n}


def metric_score(m: dict | None) -> float | None:
    """One number to compare two models' k-fold results: AUC when both classes were scored, else accuracy; lower Brier breaks ties."""
    if not m:
        return None
    base = m.get("auc") if m.get("auc") is not None else m.get("accuracy")
    if base is None:
        return None
    brier = m.get("brier_calibrated") if m.get("brier_calibrated") is not None else (m.get("brier") or 0)
    return round(base - 0.001 * brier, 5)


def beats(new: dict | None, current: dict | None) -> bool:
    """A new model is promoted only when its k-fold score is at least the current one's (ties go to the model with more data)."""
    a, b = metric_score(new), metric_score(current)
    return a is not None and (b is None or a >= b)
