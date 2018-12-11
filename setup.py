import setuptools

setuptools.setup(
    use_scm_version=True,
    package_dir={"": "src"},
    packages=setuptools.find_packages("src"),
)
