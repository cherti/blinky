#!/usr/bin/env python3

import argparse, sys
from package_tree import Package
from pacman import install_repo_packets, remove_packets
import utils

parser = argparse.ArgumentParser(description="AUR package management made easy")
primary = parser.add_mutually_exclusive_group()
primary.add_argument("-S", action='store_true', default=False, dest='install', help="Install package(s) from AUR")
primary.add_argument("-Ss", action='store_true', default=False, dest='search', help="Search for package(s) in AUR")
primary.add_argument("-Si", action='store_true', default=False, dest='info', help="Get detailed info on packages in AUR")
primary.add_argument("-Syu", action='store_true', default=False, dest='upgrade', help="Upgrade all out-of-date AUR-packages")
parser.add_argument("--asdeps", action='store_true', default=False, dest='asdeps', help="If packages are installed, install them as dependencies")
parser.add_argument("pkg_candidates", metavar="pkgname", type=str, nargs="+", help="packages to install/build")

args = parser.parse_args()

packages = []
aurpkgs, repopkgs, notfoundpkgs = utils.check_in_aur(args.pkg_candidates)

print(" :: {} are packaged in repos, skipping; use pacman to install".format(repopkgs))
print(" :: {} could not be found at all, skipping".format(notfoundpkgs))

for p in aurpkgs:
	packages.append(Package(p))

for p in packages:
	p.review()

makedeps = set()
for p in packages:
	p.get_makedeps()
	makedeps.union(p.get_makedeps())

repodeps = set()
for p in packages:
	repodeps.union(p.get_repodeps())

print(" :: installing makedeps from repos: {}".format(", ".join(makedeps))
install_repo_packets([p for p in makedeps if not p.installed and p.in_repos], asdeps=True)

print(" :: installing dependencies from repos: {}".format(", ".join(makedeps))
install_repo_packets([p for p in repodeps if not p.installed], asdeps=True)



