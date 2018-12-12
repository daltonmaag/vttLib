import setuptools

setuptools.setup(
    use_scm_version=True,
    # Do package discovery here until https://github.com/pypa/setuptools/issues/1136
    # is fixed or Python 2 support is dropped.
    package_dir={"": "src"},
    packages=setuptools.find_packages("src"),
)
