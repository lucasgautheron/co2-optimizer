from setuptools import setup, find_packages
import os


requires = {
    "core": ["PyYAML"],
    "math": ["numpy", "cvxpy", "scipy"]
}

setup(
    name="optimizer",
    version="0.0.1",
    author="Lucas Gautheron",
    author_email="lucas.gautheron@gmail.com",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=requires["core"] + requires["math"],
    zip_safe=False,
)
