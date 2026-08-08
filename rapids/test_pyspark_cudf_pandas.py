import importlib.metadata as md

packages = {
    "pyspark": "pyspark",
    "pandas": "pandas",
    "pyarrow": "pyarrow",
    "cudf-cu13": "cudf"
}

for dist_name, import_name in packages.items():
    try:
        version = md.version(dist_name)
        print(f"{dist_name}: installed, version {version}")
    except md.PackageNotFoundError:
        print(f"{dist_name}: NOT installed")

print("\nImport test:")

for dist_name, import_name in packages.items():
    try:
        module = __import__(import_name)
        print(f"{import_name}: import OK")
    except Exception as e:
        print(f"{import_name}: import FAILED -> {type(e).__name__}: {e}")
