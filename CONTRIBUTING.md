# Contributing

1. Branch from a reviewed version and create a virtual environment.
2. Install `python -m pip install '.[dev,camera,hardware]'`.
3. Make a focused change with a meaningful test or runnable example.
4. Run `python -m unittest discover -s tests -v` and `python -m build`.
5. Open a pull request explaining the problem, resulting behavior, evidence and limitations.

Distinguish implemented software, simulation and missing hardware capabilities. Avoid hard-coded success reports, silent device fallback, automatic package installation, arbitrary code-string execution and unsupported clinical claims. Medical-device integration requires an actual authorized specification and appropriate expert review; invented commands are not an implementation.

Use synthetic or appropriately licensed/de-identified data. Do not commit patient records/images, microphone recordings, credentials or signing keys. Review licenses for dependencies, models and assets. Contributions use the repository's MIT license unless explicitly agreed otherwise.
