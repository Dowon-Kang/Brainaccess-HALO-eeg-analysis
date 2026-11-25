"""RGB EEG classification pipeline applying the 9 ML improvement factors.

  1 데이터 양       : training-only augmentation (time-shift crops + Gaussian noise)
  2 특징 표현       : ERP window means / log band-power / xDAWN-covariance tangent space
  3 특징 선택       : mutual-information SelectKBest / RFE / PCA
  4 분류기          : shrinkage-LDA / SVM / Riemannian MDM / TS + logistic regression
  5 정규화          : LDA shrinkage, SVM C, standard scaling
  6 튜닝            : nested GridSearchCV (inner loop grouped by session)
  7 분포 차이       : Euclidean Alignment per session (label-free)
  8 앙상블          : soft voting / stacking
  9 평가            : leave-one-session-out, balanced accuracy, permutation test, binomial chance
"""
import numpy as np
from scipy import signal, stats
from sklearn import set_config
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin, clone
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.ensemble import StackingClassifier, VotingClassifier
from sklearn.feature_selection import RFE, SelectKBest, mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, GroupKFold, LeaveOneGroupOut, cross_val_predict, permutation_test_score
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, LinearSVC
from pyriemann.classification import MDM
from pyriemann.estimation import Covariances, XdawnCovariances
from pyriemann.tangentspace import TangentSpace


# ----------------------------------------------------------------------------- preprocessing
TMIN, TMAX, MARGIN = -0.2, 3.0, 0.08   # obs phase = 3 s colour; margin for shift augmentation


def preprocess_continuous(eeg, sfreq, l_freq=0.5, h_freq=30.0, notch=60.0):
    sos = signal.butter(4, [l_freq, h_freq], btype="band", fs=sfreq, output="sos")
    x = signal.sosfiltfilt(sos, eeg - eeg.mean(1, keepdims=True), axis=1)
    if notch and notch < sfreq / 2:
        b, a = signal.iirnotch(notch, 30, fs=sfreq)
        x = signal.filtfilt(b, a, x, axis=1)
    return x


def epoch(x, t, sfreq, marker_times, labels, contact=None, ptp_uv=150.0):
    """Cut epochs [TMIN-MARGIN, TMAX+MARGIN], baseline-correct on [TMIN, 0]."""
    n0 = int(round((TMIN - MARGIN) * sfreq))
    n1 = int(round((TMAX + MARGIN) * sfreq))
    base = slice(int(round(MARGIN * sfreq)), int(round((MARGIN - TMIN) * sfreq)))
    core = slice(int(round(MARGIN * sfreq)), int(round((MARGIN + TMAX - TMIN) * sfreq)))
    idx = np.searchsorted(t, marker_times)
    X, y, keep, reasons = [], [], [], {"edge": 0, "ptp": 0, "contact": 0}
    for i, (k, lab) in enumerate(zip(idx, labels)):
        if k + n0 < 0 or k + n1 > x.shape[1]:
            reasons["edge"] += 1
            continue
        ep = x[:, k + n0:k + n1].copy()
        ep -= ep[:, base].mean(1, keepdims=True)
        if contact is not None and (contact[:, k + n0:k + n1] == 0).any():
            reasons["contact"] += 1
            continue
        if np.ptp(ep[:, core], axis=1).max() > ptp_uv:
            reasons["ptp"] += 1
            continue
        X.append(ep); y.append(lab); keep.append(i)
    return np.array(X), np.array(y), np.array(keep), reasons


def euclidean_align(X):
    """He & Wu EA: whiten each session so its mean covariance becomes identity (label-free)."""
    R = np.mean([e @ e.T / e.shape[1] for e in X], axis=0)
    w, V = np.linalg.eigh(R)
    Rinv = V @ np.diag(1.0 / np.sqrt(np.maximum(w, 1e-12))) @ V.T
    return np.einsum("ij,njt->nit", Rinv, X)


def apply_ea_per_group(X, groups):
    Xa = np.empty_like(X)
    for g in np.unique(groups):
        m = groups == g
        Xa[m] = euclidean_align(X[m])
    return Xa


# ----------------------------------------------------------------------------- transformers
class Crop(BaseEstimator, TransformerMixin):
    """Remove the augmentation margin (offset in samples, 0 = centred)."""
    def __init__(self, sfreq=250.0, offset=0):
        self.sfreq, self.offset = sfreq, offset

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        m = int(round(MARGIN * self.sfreq))
        n = int(round((TMAX - TMIN) * self.sfreq))
        s = m + self.offset
        return X[:, :, s:s + n]


class TimeWindow(BaseEstimator, TransformerMixin):
    def __init__(self, sfreq=250.0, tmin=0.3, tmax=3.0):
        self.sfreq, self.tmin, self.tmax = sfreq, tmin, tmax

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X[:, :, int(round((self.tmin - TMIN) * self.sfreq)):int(round((self.tmax - TMIN) * self.sfreq))]


class ERPWindowMeans(BaseEstimator, TransformerMixin):
    def __init__(self, sfreq=250.0, start=0.05, stop=0.5, width=0.05, picks=None):
        self.sfreq, self.start, self.stop, self.width, self.picks = sfreq, start, stop, width, picks

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        Xp = X if self.picks is None else X[:, self.picks]
        feats = []
        for a in np.arange(self.start, self.stop - 1e-9, self.width):
            i0 = int(round((a - TMIN) * self.sfreq))
            i1 = int(round((a + self.width - TMIN) * self.sfreq))
            feats.append(Xp[:, :, i0:i1].mean(2))
        return np.concatenate(feats, axis=1)


class LogBandPower(BaseEstimator, TransformerMixin):
    BANDS = ((1, 4), (4, 8), (8, 13), (13, 20), (20, 30))

    def __init__(self, sfreq=250.0, tmin=0.0):
        self.sfreq, self.tmin = sfreq, tmin

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        i0 = int(round((self.tmin - TMIN) * self.sfreq))
        f, P = signal.welch(X[:, :, i0:], fs=self.sfreq, nperseg=min(128, X.shape[2] - i0), axis=-1)
        out = [np.log(P[:, :, (f >= lo) & (f < hi)].mean(-1) + 1e-12) for lo, hi in self.BANDS]
        return np.concatenate(out, axis=1)


class AugmentedClassifier(BaseEstimator, ClassifierMixin):
    """Factor 1: augment ONLY the training fold (shifted crops + noise), then fit `estimator`.
    `estimator` must start with a Crop step named 'crop'."""
    def __init__(self, estimator=None, shifts=(-10, -5, 5, 10), noise_sd=0.1, seed=0):
        self.estimator, self.shifts, self.noise_sd, self.seed = estimator, shifts, noise_sd, seed

    def fit(self, X, y):
        rng = np.random.default_rng(self.seed)
        crop = self.estimator.steps[0][1]
        Xs, ys = [crop.set_params(offset=0).transform(X)], [y]
        for s in self.shifts:
            Xs.append(crop.set_params(offset=s).transform(X)); ys.append(y)
        crop.set_params(offset=0)
        Xa = np.concatenate(Xs)
        Xa = Xa + rng.normal(0, self.noise_sd, Xa.shape) * Xa.std(axis=(0, 2), keepdims=True)
        self.inner_ = clone(self.estimator)
        self.inner_.steps[0] = ("crop", "passthrough")
        self.inner_.fit(Xa, np.concatenate(ys))
        self.classes_ = self.inner_.classes_
        return self

    def predict(self, X):
        return self.inner_.predict(Crop(self.estimator.steps[0][1].sfreq).transform(X))


# ----------------------------------------------------------------------------- pipelines
def pipelines(sfreq=250.0, n_classes=3):
    occ = [0, 1]  # O1, O2
    C = lambda: Crop(sfreq)
    slda = lambda: LDA(solver="lsqr", shrinkage="auto")
    P = {}
    # Factor 4/5 baseline + regularisation
    P["F2a ERP(4ch)+LDA(no shrink)"] = make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(), LDA(solver="lsqr"))
    P["F2a ERP(4ch)+sLDA"] = make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(), slda())
    P["F2a ERP(O1,O2)+sLDA"] = make_pipeline(C(), ERPWindowMeans(sfreq, picks=occ), StandardScaler(), slda())
    P["F2b BandPower+sLDA"] = make_pipeline(C(), LogBandPower(sfreq), StandardScaler(), slda())
    P["F2c xDAWN-TS+LR"] = make_pipeline(C(), TimeWindow(sfreq, -0.2, 1.0), XdawnCovariances(nfilter=2, estimator="oas"),
                                         TangentSpace(), StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    P["F2d sustained Cov-TS+LR"] = make_pipeline(C(), TimeWindow(sfreq, 0.3, 3.0), Covariances("oas"), TangentSpace(),
                                                 StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    # Factor 3 feature selection
    P["F3a ERP+MI-k20+sLDA"] = make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(),
                                             SelectKBest(mutual_info_classif, k=20), slda())
    P["F3b ERP+RFE20+sLDA"] = make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(),
                                            RFE(LinearSVC(C=0.1, max_iter=5000), n_features_to_select=20), slda())
    P["F3c ERP+PCA10+sLDA"] = make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(), PCA(10), slda())
    # Factor 4 classifiers
    P["F4a ERP+SVM-linear"] = make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(), SVC(kernel="linear", C=0.1, probability=True))
    P["F4b ERP+SVM-RBF"] = make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(), SVC(kernel="rbf", C=1.0, probability=True))
    P["F4c xDAWN-cov+MDM"] = make_pipeline(C(), TimeWindow(sfreq, -0.2, 1.0), XdawnCovariances(nfilter=2, estimator="oas"), MDM())
    # Factor 1 augmentation (train folds only)
    P["F1 ERP+sLDA +augment"] = AugmentedClassifier(make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(), slda()))
    # Factor 6 nested tuning (inner GroupKFold over training blocks only)
    inner = make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(), SelectKBest(mutual_info_classif), slda())
    grid = {"erpwindowmeans__width": [0.025, 0.05, 0.1], "erpwindowmeans__stop": [0.35, 0.5],
            "selectkbest__k": [8, 16, "all"]}
    P["F6 nested-tuned ERP+sLDA"] = GridSearchCV(inner, grid, cv=GroupKFold(5), scoring="balanced_accuracy",
                                                 n_jobs=1)
    # Factor 8 ensembles
    members = [("erp", make_pipeline(C(), ERPWindowMeans(sfreq), StandardScaler(), slda())),
               ("ts", make_pipeline(C(), TimeWindow(sfreq, -0.2, 1.0), XdawnCovariances(nfilter=2, estimator="oas"), TangentSpace(), StandardScaler(),
                                    LogisticRegression(max_iter=2000))),
               ("bp", make_pipeline(C(), LogBandPower(sfreq), StandardScaler(), slda()))]
    P["F8a soft-voting(ERP,TS,BP)"] = VotingClassifier(members, voting="soft")
    P["F8b stacking(ERP,TS,BP)"] = StackingClassifier(members, final_estimator=LogisticRegression(max_iter=2000), cv=3)
    return P


# ----------------------------------------------------------------------------- evaluation (factor 9)
def binomial_chance(n, n_classes, alpha=0.05):
    return stats.binom.ppf(1 - alpha, n, 1.0 / n_classes) / n


def _fit(pipe, X, y, g):
    est = clone(pipe)
    if isinstance(est, GridSearchCV):
        est.set_params(cv=GroupKFold(min(5, len(np.unique(g)))))
        est.fit(X, y, groups=g)          # inner loop splits TRAIN blocks only
    else:
        est.fit(X, y)
    return est


def evaluate(pipe, X, y, groups):
    """Outer leave-one-session-out. Everything (scaler, selection, xDAWN, augmentation, tuning)
    is fit inside the training fold only."""
    pred = np.empty_like(y)
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        pred[te] = _fit(pipe, X[tr], y[tr], groups[tr]).predict(X[te])
    per_fold = [balanced_accuracy_score(y[groups == g], pred[groups == g]) for g in np.unique(groups)]
    return balanced_accuracy_score(y, pred), np.array(per_fold), pred


def permutation_p(pipe, X, y, groups, n_perm=100, seed=0):
    """Labels shuffled WITHIN each session, full outer CV re-run each time."""
    rng = np.random.default_rng(seed)
    score = evaluate(pipe, X, y, groups)[0]
    perm = []
    for _ in range(n_perm):
        yp = y.copy()
        for g in np.unique(groups):
            m = np.where(groups == g)[0]; yp[m] = rng.permutation(yp[m])
        perm.append(evaluate(pipe, X, yp, groups)[0])
    perm = np.array(perm)
    return score, perm, (np.sum(perm >= score) + 1) / (n_perm + 1)
