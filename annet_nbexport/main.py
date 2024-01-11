#!/usr/bin/env python3

import argparse
import asyncio
import os
import typing

import aiohttp
import yarl


async def download(url: yarl.URL, dest: typing.BinaryIO):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            async for b in resp.content.iter_any():
                dest.write(b)


async def download_devices(url: yarl.URL, region: str):
    basedir = os.path.dirname(__file__)
    regiondir = os.path.join(basedir, "data", region)
    os.makedirs(regiondir, exist_ok=True)
    with open(os.path.join(regiondir, "devices.csv"), "wb") as fh:
        await download(url.with_path("/dcim/devices/").with_query("export"), fh)


async def amain():
    p = argparse.ArgumentParser()
    p.add_argument("--region-name", default=None, help="The name of the region to download cvs to")
    p.add_argument("netbox_url", type=yarl.URL, help="The URL to access netbox API")
    args = p.parse_args()

    if args.region_name is None:
        region_name = args.netbox_url.host
    else:
        region_name = args.region_name

    await download_devices(args.netbox_url, region_name)


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
