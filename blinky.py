#!/usr/bin/env python3

import argparse, sys, os
from collections import namedtuple
from package_tree import Package
from pacman import install_repo_packets, remove_packets, install_package_files
import utils

Context = namedtuple('Context', ['cachedir', 'builddir'])

parser = argparse.ArgumentParser(description="AUR package management made easy")
primary = parser.add_mutually_exclusive_group()
primary.add_argument("-S", action='store_true', default=False, dest='install', help="Install package(s) from AUR")
primary.add_argument("-Ss", action='store_true', default=False, dest='search', help="Search for package(s) in AUR")
primary.add_argument("-Si", action='store_true', default=False, dest='info', help="Get detailed info on packages in AUR")
primary.add_argument("-Syu", action='store_true', default=False, dest='upgrade', help="Upgrade all out-of-date AUR-packages")
parser.add_argument("--asdeps", action='store_true', default=False, dest='asdeps', help="If packages are installed, install them as dependencies")
parser.add_argument("--local-path", action='store', default='~/.blinky', dest='aur_local', help="Local path for building and cache")
parser.add_argument("pkg_candidates", metavar="pkgname", type=str, nargs="+", help="packages to install/build")

args = parser.parse_args()

# process arguments if necessary
args.aur_local = os.path.abspath(os.path.expanduser(args.aur_local))

ctx = Context(cachedir=os.path.join(args.aur_local, 'cache'), builddir=os.path.join(args.aur_local, 'build'))
os.makedirs(ctx.cachedir, exist_ok=True)
os.makedirs(ctx.builddir, exist_ok=True)


def build_packages_from_aur(package_candidates):
	aurpkgs, repopkgs, notfoundpkgs = utils.check_in_aur(package_candidates)

	if repopkgs:
		print(" :: Skipping packages {}: packaged in repos, use pacman to install".format(", ".join(repopkgs)))
	if notfoundpkgs:
		print(" :: Skipping packages {}: could not be found in either repos or AUR".format(", ".join(notfoundpkgs)))

	packages = []
	for p in aurpkgs:
		packages.append(Package(p, ctx=ctx))

	for p in packages:
		if not p.review():
			print(" :: Skipping packages {}: Did not pass review".format(p.name))
			packages.remove(p)


	uninstalled_makedeps = set()
	for p in packages:
		md = p.get_makedeps()
		md_not_found = [p for p in md if not p.installed and not p.in_repos and not p.in_aur]
		if len(md_not_found) > 0:
			print(" :: Skipping {}: cannot satisfy makedeps from repos, AUR or local installed packages".format(p.name))
			packages.remove(p)

		md_available = set([p for p in md if not p.installed and (p.in_repos or p.in_aur)])

		uninstalled_makedeps = uninstalled_makedeps.union(md_available)

	md_aur = [p for p in uninstalled_makedeps if p.in_aur]
	if len(md_aur) > 0:
		print(" :: Building makedeps from aur: {}".format(", ".join(md_aur)))
		build_packages_from_aur(md_aur)

	repodeps = set()
	for p in packages:
		repodeps = repodeps.union(p.get_repodeps())

	md_repos = [p.name for p in uninstalled_makedeps if p.in_repos]
	print(" :: Installing makedeps from repos: {}".format(", ".join(md_repos)))
	install_repo_packets(md_repos, asdeps=True)


	repodeps_uninstalled = [p.name for p in repodeps if not p.installed]
	print(" :: Installing dependencies from repos: {}".format(", ".join(repodeps_uninstalled)))
	install_repo_packets(repodeps_uninstalled, asdeps=True)

	for p in packages:
		p.build()

	built_pkgs = set()
	built_deps = set()
	for p in packages:
		built_pkgs = built_pkgs.union(set(p.built_pkgs))
		for d in p.deps:
			built_deps = built_deps.union(d.get_built_pkgs())

	os.chdir(ctx.cachedir)
	print(" :: installing built package dependencies: {}".format(", ".join(built_deps)))
	install_package_files(built_deps, asdeps=True)
	print(" :: installing built packages: {}".format(", ".join(built_pkgs)))
	install_package_files(built_pkgs, asdeps=False)


	print(" :: removing previously uninstalled makedeps: {}".format(", ".join(uninstalled_makedeps)))
	remove_packets(uninstalled_makedeps)


if __name__ == "__main__":
	build_packages_from_aur(args.pkg_candidates)
