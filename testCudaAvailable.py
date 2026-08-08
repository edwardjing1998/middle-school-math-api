import sys
from numba import cuda

print("Python executable:", sys.executable)
print("CUDA available:", cuda.is_available())