#!/usr/bin/env python3

import argparse, sys, os
from collections import namedtuple
from package_tree import Package
import pacman, utils

Context = namedtuple('Context', ['cachedir', 'builddir'])

parser = argparse.ArgumentParser(description="AUR package management made easy")
primary = parser.add_mutually_exclusive_group()
primary.add_argument("-S", action='store_true', default=False, dest='install', help="Install package(s) from AUR")
primary.add_argument("-Ss", action='store_true', default=False, dest='search', help="Search for package(s) in AUR")
primary.add_argument("-Si", action='store_true', default=False, dest='info', help="Get detailed info on packages in AUR")
primary.add_argument("-Syu", action='store_true', default=False, dest='upgrade', help="Upgrade all out-of-date AUR-packages")
parser.add_argument("--asdeps", action='store_true', default=False, dest='asdeps', help="If packages are installed, install them as dependencies")
parser.add_argument("--local-path", action='store', default='~/.blinky', dest='aur_local', help="Local path for building and cache")
parser.add_argument("pkg_candidates", metavar="pkgname", type=str, nargs="*", help="packages to install/build")

args = parser.parse_args()

# process arguments if necessary
args.aur_local = os.path.abspath(os.path.expanduser(args.aur_local))

ctx = Context(cachedir=os.path.join(args.aur_local, 'cache'), builddir=os.path.join(args.aur_local, 'build'))
os.makedirs(ctx.cachedir, exist_ok=True)
os.makedirs(ctx.builddir, exist_ok=True)
print("builddir:", ctx.builddir)
print("cachedir:", ctx.cachedir)


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
	repodeps_uninstalled = [p.name for p in repodeps if not p.installed]
	to_be_installed = set(repodeps_uninstalled).union(md_repos)
	print(" :: Installing dependencies and makedeps from repos: {}".format(", ".join(to_be_installed)))
	if not pacman.install_repo_packages(to_be_installed, asdeps=True):
		utils.logerr(0, "Could not install deps and makedeps from repos")

	for p in packages:
		p.build()

	built_pkgs = set()
	built_deps = set()
	for p in packages:
		built_pkgs = built_pkgs.union(set(p.built_pkgs))
		for d in p.deps:
			built_deps = built_deps.union(d.get_built_pkgs())

	os.chdir(ctx.cachedir)

	if built_deps:
		print(" :: installing built package dependencies: {}".format(", ".join(built_deps)))
		if not pacman.install_package_files(built_deps, asdeps=True):
			utils.logerr(2, "Failed to install built package dependencies")

	print(" :: installing built packages: {}".format(", ".join(built_pkgs)))
	if not pacman.install_package_files(built_pkgs, asdeps=False):
		utils.logerr(2, "Failed to install built packages")


	print(" :: removing previously uninstalled makedeps: {}".format(", ".join(uninstalled_makedeps)))
	if not pacman.remove_packages(uninstalled_makedeps):
		utils.logerr(None, "Failed to remove previously uninstalled makedeps")


if __name__ == "__main__":
	if args.install:
		build_packages_from_aur(args.pkg_candidates)
	if args.search:
		aurdata = utils.query_aur("search", args.pkg_candidates)
		if aurdata["resultcount"] == 0:
			print(" :: no results found")
		else:
			for pkgdata in aurdata["results"]:
				print("aur/{} {}".format(pkgdata["Name"], pkgdata["Version"]))
				print("    " + pkgdata["Description"])
	if args.info:
		from templates import pkginfo
		foundSth = False
		for pkg in args.pkg_candidates:
			print("checking pkg", pkg)
			pkgdata = utils.query_aur("info", pkg, single=True)
			if pkgdata:
				foundSth = True
				print(pkginfo.format(
						name=pkgdata.get("Name"),
						version=pkgdata.get("Version"),
						desc=pkgdata.get("Description"),
						url=pkgdata.get("URL"),
						license=", ".join(pkgdata.get("License") or ["None"]),
						groups=", ".join(pkgdata.get("Groups") or ["None"]),
						provides=", ".join(pkgdata.get("Provides") or ["None"]),
						deps=", ".join(pkgdata.get("Depends") or ["None"]),
						optdeps=", ".join(pkgdata.get("OptDepends") or ["None"]),
						makedeps=", ".join(pkgdata.get("MakeDepends") or ["None"]),
						conflicts=", ".join(pkgdata.get("Conflicts") or ["None"]),
						replaces=", ".join(pkgdata.get("Replaces") or ["None"]),
						maintainer=pkgdata.get("Maintainer"),
						submitted=pkgdata.get("FirstSubmitted"),
						numvotes=pkgdata.get("NumVotes"),
						popularity=pkgdata.get("Popularity"),
						outofdate=pkgdata.get("OutOfDate") or "No"
						))

		if not foundSth:
			print(" :: no results found")

	if args.upgrade:
		foreign_pkg_v = pacman.get_foreign_package_versions()
		aurdata = utils.query_aur("info", foreign_pkg_v.keys())
		upgradable_pkgs = []
		for pkgdata in aurdata["results"]:
			if pkgdata["Name"] in foreign_pkg_v:
				if pkgdata["Version"] > foreign_pkg_v[pkgdata["Name"]]:
					upgradable_pkgs.append(pkgdata["Name"])

		build_packages_from_aur(upgradable_pkgs)

