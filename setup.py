from setuptools import setup, find_packages

setup(
    name="plex_sync",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    py_modules=["plex_sync"],
    install_requires=[
        "Click",
    ],
    entry_points={
        "console_scripts": [
            "plex-sync = plex_sync:main:cli",
        ],
    },
)
