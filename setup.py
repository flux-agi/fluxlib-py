from setuptools import setup, find_packages

setup(
    name="fluxlib",
    version="0.3.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[],
)