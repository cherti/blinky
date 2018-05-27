#!/usr/bin/env python3

import requests, sys
import pacman

def AmbiguousPacketName(Exception):
	pass

def UnknownAURQueryType(Exception):
	pass

def logerr(code, msg):
	print(" !> {}".format(msg), file=sys.stderr)
	if code:
		exit(code)

def logmsg(msg):
	print(" :: {}".format(msg))

def query_aur(query_type, arg, single=False):
	if query_type not in ["info", "search"]:
		raise UnknownAURQueryType("query {} is not a valid query type".format(query_type))

	arg = [arg] if type(arg) != list else arg

	arg_type = "arg[]" if query_type == "info" else "arg"
	r = requests.get("https://aur.archlinux.org/rpc/", params={"type": query_type, "v":5, arg_type:arg})
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
		aurpkgs.append(pkg["Name"])
		pkgs.remove(pkg["Name"])

	for pkg in pkgs:
		if pacman.in_repos(pkg):
			repopkgs.append(pkg)
			pkgs.remove(pkg)

	# return aurpkgs, repopkgs, not_found_anywhere_pkgs
	return aurpkgs, repopkgs, pkgs


def install_built_packages(pkgs):
	print("would install now: {}".format(pkgs.join(", ")))
