#!/usr/bin/env python3


from setuptools import find_packages, setup


setup(
    author="Amazon Web Services",
    install_requires=["boto3"],
    license="MIT-0",
    name="ecomshared",
    packages=find_packages(),
    setup_requires=["pytest-runner"],
    test_suite="tests",
    tests_require=["pytest"],
    version="0.1.3"
)