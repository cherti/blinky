#!/usr/bin/env python3

import requests, sys, os, stat
import termcolor
from blinky import pacman

def AmbiguousPacketName(Exception):
	pass

def UnknownAURQueryType(Exception):
	pass

class UnsatisfiableDependencyError(Exception):
	pass

class APIError(Exception):
	def __init__(self, msg, type):
		self.message = msg
		self.type = type


def logerr(code, msg):
	print(termcolor.colored(" !> {}".format(msg), color='red'), file=sys.stderr)
	if code:
		print(termcolor.colored(" --> Fatal, exiting".format(msg), color='red', attrs=["bold"]), file=sys.stderr)
		exit(code)

def logmsg(verbosity_level, required_level, msg):
	if verbosity_level >= required_level:
		if required_level == 0:
			print(termcolor.colored(" :: {}".format(msg), attrs=["bold"]))
		else:
			print(" :: {}".format(msg))


def delete_onerror(func, path, excinfo):
	os.chmod(path, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
	if os.path.isdir(path):
		os.rmdir(path)
	else:
		os.remove(path)


def query_aur(query_type, arg, single=False):
	if query_type not in ["info", "search"]:
		raise UnknownAURQueryType("query {} is not a valid query type".format(query_type))

	arg = [arg] if type(arg) != list else arg

	arg_type = "arg[]" if query_type == "info" else "arg"
	r = requests.get("https://aur.archlinux.org/rpc/", params={"type": query_type, "v":5, arg_type:arg})
	if r.status_code == 429:
		raise APIError("Rate limit of AUR-API hit", "ratelimit")
	elif r.status_code == 503:
		raise APIError("AUR-API currently not available", "unavailable")

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


def query_aur_exit_on_error(query_type, arg, single=False):
	try:
		return query_aur(query_type, arg, single=single)
	except APIError as e:
		if e.type == 'ratelimit':
			logerr(5, "Your IP seems to be ratelimited by the AUR-API. Try again tomorrow.")
		elif e.type == 'unavailable':
			logerr(6, "AUR-API currently unavailable, try again later.")


def check_in_aur(pkgs):
	r = query_aur("info", pkgs)
	if r["resultcount"] == len(pkgs):
		return pkgs, [], []

	aurpkgs, repopkgs = [], []
	for pkg in r["results"]:
		aurpkgs.append(pkg["Name"])
		pkgs.remove(pkg["Name"])

	for pkg in pkgs:
		if pacman.find_satisfier_in_syncdbs(pkg):
			repopkgs.append(pkg)
			pkgs.remove(pkg)

	# return aurpkgs, repopkgs, not_found_anywhere_pkgs
	return aurpkgs, repopkgs, pkgs


def install_built_packages(pkgs):
	print("would install now: {}".format(pkgs.join(", ")))
