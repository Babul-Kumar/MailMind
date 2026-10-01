from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from backend.app.ml.priority import PRIORITY_MAPPING


def extract_feature_signals(
    pipeline,
    text: str,
    predicted_class: str,
    max_terms: int = 5,
    X_row: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Extracts positive feature contributions for the predicted class from the
    trained Logistic Regression model weights: weight = X[0, j] * coef[class_idx, j].
    Strictly grounded in model parameters; never invents external signals.
    Reuses pre-transformed X_row if available to avoid redundant TF-IDF transformations.
    """
    signals = []
    try:
        tfidf = pipeline.named_steps.get('tfidf')
        clf = pipeline.named_steps.get('clf')
        if not tfidf or not clf or not hasattr(clf, 'coef_') or not hasattr(tfidf, 'get_feature_names_out'):
            return []

        classes = list(clf.classes_)
        if predicted_class not in classes:
            return []

        class_idx = classes.index(predicted_class)
        feature_names = getattr(pipeline, "_cached_feature_names", None)
        if feature_names is None:
            feature_names = np.array(tfidf.get_feature_names_out())
            try:
                setattr(pipeline, "_cached_feature_names", feature_names)
            except Exception:
                pass

        if X_row is not None:
            indices = X_row.indices
            data = X_row.data
        else:
            X = tfidf.transform([text]).tocsr()
            indices = X.indices
            data = X.data

        if len(indices) == 0:
            return []

        contributions = []
        for i, idx in enumerate(indices):
            contrib = data[i] * clf.coef_[class_idx, idx]
            if contrib > 0.001:  # Positive evidence supporting predicted class
                contributions.append((feature_names[idx], float(contrib)))

        contributions.sort(key=lambda x: x[1], reverse=True)
        for term, weight in contributions[:max_terms]:
            signals.append({'term': term, 'weight': round(weight, 4)})
    except Exception:
        pass

    return signals


def explain_prediction(
    pipeline,
    text: str,
    predicted_class: str,
    confidence: float,
    max_terms: int = 4,
    X_row: Optional[Any] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generates a transparent, model-grounded explanation based on the predicted class,
    model confidence, and positive TF-IDF n-gram feature contributions from the classifier weights.
    Appends a low-confidence advisory if confidence is relatively low (< 0.40).
    """
    priority_name = PRIORITY_MAPPING.get(predicted_class, predicted_class)
    base_explanation = f"Model classified this email as {priority_name} (model confidence: {confidence*100:.1f}%)."

    signals = extract_feature_signals(pipeline, text, predicted_class, max_terms=max_terms, X_row=X_row)

    if signals:
        terms_str = ", ".join([f"'{s['term']}'" for s in signals])
        explanation = f"{base_explanation} Key model signals: {terms_str}."
    else:
        explanation = f"{base_explanation} Key signals are distributed across general vocabulary."

    if confidence < 0.40:
        explanation += " (Note: Model confidence is relatively low; review email context)."

    return explanation, signals
