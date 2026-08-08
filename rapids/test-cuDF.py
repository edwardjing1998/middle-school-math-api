import cudf

print("cuDF version:", cudf.__version__)

s = cudf.Series([1, 2, 3, 4, 5])
print(s)
print("sum =", s.sum())