#!/usr/bin/env python3

import argparse

parser = argparse.ArgumentParser(description="AUR package management made easy")
primary = parser.add_mutually_exclusive_group()
primary.add_argument("-S", action='store_true', default=False, dest='install', help="Install package(s) from AUR")
primary.add_argument("-Ss", action='store_true', default=False, dest='search', help="Search for package(s) in AUR")
primary.add_argument("-Si", action='store_true', default=False, dest='info', help="Get detailed info on packages in AUR")
primary.add_argument("-Syu", action='store_true', default=False, dest='upgrade', help="Upgrade all out-of-date AUR-packages")
parser.add_argument("--asdeps", action='store_true', default=False, dest='asdeps', help="If packages are installed, install them as dependencies")
parser.add_argument("pkgs", metavar="pkgname", type=str, nargs="+", help="packages to install/build")

args = parser.parse_args()

