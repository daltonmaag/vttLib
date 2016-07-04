import sys
import setuptools


name = "vttLib"
description = "Compile Visual TrueType assembly with FontTools."

needs_pytest = {'pytest', 'test'}.intersection(sys.argv)
pytest_runner = ['pytest_runner'] if needs_pytest else []
needs_wheel = {'release', 'bdist_wheel'}.intersection(sys.argv)
wheel = ['wheel'] if needs_wheel else []

setup_params = dict(
    name=name,
    use_scm_version=True,
    description=description,
    author="Dalton Maag Ltd",
    author_email="info@daltonmaag.com",
    license="MIT",
    package_dir={"": "src"},
    packages=setuptools.find_packages(),
    include_package_data=True,
    setup_requires=[
        'setuptools_scm>=1.9',
    ] + pytest_runner + wheel,
    tests_require=[
        'pytest>=2.8',
    ],
)


if __name__ == '__main__':
    setuptools.setup(**setup_params)
