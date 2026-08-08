import cudf
from cuml.linear_model import LinearRegression

df = cudf.DataFrame({
    "x": [1, 2, 3, 4],
    "y": [2, 4, 6, 8]
})

X = df[["x"]]
y = df["y"]

model = LinearRegression()
model.fit(X, y)

print(model.predict(X))