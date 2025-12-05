import numpy as np
from sklearn.linear_model import Ridge


def test_minimal():
    # Create synthetic data mimicking our range
    x = np.random.uniform(-0.5, 0.7, (1000, 4))
    y = np.random.uniform(-60, 80, (1000,))

    model = Ridge(alpha=1.0)
    model.fit(x, y)

    print("Coefficients:", model.coef_)
    print("Intercept:", model.intercept_)

    preds = model.predict(x)
    print("Predictions mean:", preds.mean())


if __name__ == "__main__":
    test_minimal()
