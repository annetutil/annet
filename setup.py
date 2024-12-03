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
        ]),
        package_data={
            "annet": ["configs/*"],
            "annet.rulebook": ["texts/*.rul", "texts/*.order", "texts/*.deploy"],
            "annet.annlib.netdev.devdb": ["data/*.json"],
        },
        entry_points={
          "console_scripts": [
              "annet = annet.annet:main",
          ],
          "annet.connectors": [
            "storage = annet.adapters.netbox.provider:NetboxProvider",
          ],
          "annet.connectors.storage": [
            "file = annet.adapters.file.provider:Provider",
          ],
        },
        extras_require={
            "netbox": ["annetbox[sync]>=0.1.10"],
        },
        python_requires=">=3.10",
        install_requires=requirements(),
        include_package_data=True,
    )
