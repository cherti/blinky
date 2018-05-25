#!/usr/bin/env python3

import requests
from pacman import in_repos

def AmbiguousPacketName(Exception):
	pass

def UnknownAURQueryType(Exception):
	pass

def query_aur(query_type, arg, single=False):
	if query_type not in ["info", "search"]:
		raise UnknownAURQueryType("query {} is not a valid query type".format(query_type))

	arg = arg[0] if single and type(arg) == list else arg

	r = requests.get("https://aur.archlinux.org/rpc/", params={"type": query_type, "v":5, "arg":arg})
	aurdata = r.json()
	if single:
		if type == "info" and aurdata["resultcount"] > 1:
			raise AmbiguousPacketName("Package name {} is ambiguous for some reason, please consider a bug report".format(arg))
		elif aurdata["resultcount"] == 1:
			return aurdata["results"][0]
		else:
			return None
	else:
		return aurdata


def check_in_aur(pkgs):
	r = query_aur("info", pkgs)
	if r["resultcount"] == len(pkgs):
		return pkgs, [], []

	aurpkgs, repopkgs = [], []
	for pkg in r["results"]:
		aurpkgs += pkg["Name"]
		pkgs    += pkg["Name"]

	for pkg in pkgs:
		if in_repos(pkg):
			repopkgs += pkg
			pkgs.remove(pkg)

	# return aurpkgs, repopkgs, not_found_anywhere_pkgs
	return aurpkgs, repopkgs, pkgs


def install_built_packages(pkgs):
	print("would install now: {}".format(pkgs.join(", ")))
