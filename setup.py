from setuptools import setup

setup(
    name="hamper_pokedex",
    version = "0.1",
    py_modules = ["hamper_pokedex"],

    author="Andrew Ekstedt",
    author_email="andrew.ekstedt@gmail.com",

    install_requires = ["Pokedex"],
    dependency_links = ["git+https://github.com/veekun/pokedex#egg=Pokedex-0.1"],

    entry_points = {"hamperbot.plugins": "pokedex = hamper_pokedex:Plugin"},
)
