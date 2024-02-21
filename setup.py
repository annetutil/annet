#!/usr/bin/env python3
import os
import setuptools

here = os.path.abspath(os.path.dirname(__file__))


def requirements() -> str:
    with open(os.path.join(here, "requirements.txt")) as file:
        return "".join(
            line
            for line in file.readlines()
            if not line.startswith("-")
        )


if __name__ == "__main__":
    setuptools.setup(
        name="annet",
        version=os.getenv("VERSION") or "0.0",
        description="annet",
        license="MIT",
        url="https://github.com/annetutil/annet",
        packages=setuptools.find_packages(include=[
            "annet",
            "annet.*",
            "annet_generators",
            "annet_generators.*",
            "annet_nbexport",
            "annet_nbexport.*"
        ]),
        package_data={
            "annet": ["configs/*"],
            "annet.rulebook": ["texts/*.rul", "texts/*.order", "texts/*.deploy"],
            "annet.annlib.netdev.devdb": ["data/*.json"],
        },
        entry_points={
          "console_scripts": [
              "annet = annet.annet:main",
              "annet_nbexport = annet_nbexport.main:main",
          ],
          "annet.connectors": [
            "storage = annet_nbexport:AnnetNbExportProvder",
          ],
        },
        python_requires=">=3.8",
        install_requires=requirements(),
        include_package_data=True,
    )
