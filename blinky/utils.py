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


def logerr(code, msg, primary=True):
	prefix = ' !>'
	if not primary:
		prefix = '   '

	print(termcolor.colored("{} {}".format(prefix, msg), color='red'), file=sys.stderr)
	if code:
		print(termcolor.colored(" --> Fatal, exiting".format(msg), color='red', attrs=["bold"]), file=sys.stderr)
		exit(code)

def logmsg(verbosity_level, required_level, msg, primary=True):
	prefix = ' ::'
	if not primary:
		prefix = '   '
	if verbosity_level >= required_level:
		if required_level == 0:
			print(termcolor.colored("{} {}".format(prefix, msg), attrs=["bold"]))
		else:
			print("{} {}".format(prefix, msg))


def exit_if_root():
	"""
	As makepkg will refuse to run as root, we can
	early exit on all operations that might call makepkg.
	"""
	if os.getuid() == 0:
		logmsg(0, 0, "blinky cannot not do this as root, please run it as an unprivileged user.")
		sys.exit()


def delete_onerror(func, path, excinfo):
	os.chmod(path, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
	if os.path.isdir(path):
		os.rmdir(path)
	else:
		os.remove(path)


def query_aur(query_type, arg, single=False, search_by=None, ignore_ood=False):
	if query_type not in ["info", "search"]:
		raise UnknownAURQueryType("query {} is not a valid query type".format(query_type))

	valid_search_by = search_by in ["name", "name-desc", "maintainer", "depends", "makedepends", "optdepends", "checkdepends"]

	arg = [arg] if type(arg) != list else arg

	arg_type = "arg[]" if query_type == "info" else "arg"
	query_params = {"type": query_type, "v":5, arg_type:arg}
	if query_type == "search" and valid_search_by:
		query_params["by"] = search_by

	r = requests.get("https://aur.archlinux.org/rpc/", params=query_params)
	if r.status_code == 429:
		raise APIError("Rate limit of AUR-API hit", "ratelimit")
	elif r.status_code == 503:
		raise APIError("AUR-API currently not available", "unavailable")

	aurdata = r.json()
	if ignore_ood:
		# kick out all packages flagged out-of-date
		filtered_results = []
		for i, result in enumerate(aurdata["results"]):
			if result["OutOfDate"] is None:
				filtered_results.append(result)

		aurdata["results"] = filtered_results

	if single:
		if type == "info" and aurdata["resultcount"] > 1:
			raise AmbiguousPacketName("Package name {} is ambiguous for some reason, please consider a bug report".format(arg))
		elif aurdata["resultcount"] == 1:
			return aurdata["results"][0]
		else:
			return None
	else:
		return aurdata


def query_aur_exit_on_error(query_type, arg, single=False, search_by=None, ignore_ood=False):
	try:
		return query_aur(query_type, arg, single=single, search_by=search_by, ignore_ood=ignore_ood)
	except APIError as e:
		if e.type == 'ratelimit':
			logerr(5, "Your IP seems to be ratelimited by the AUR-API. Try again tomorrow.")
		elif e.type == 'unavailable':
			logerr(6, "AUR-API currently unavailable, try again later.")


def check_in_aur(pkgs):
	r = query_aur("info", pkgs)

	aurpkgs, repopkgs = [], []
	pkg2aurdata = {}
	for pkg in r["results"]:
		aurpkgs.append(pkg["Name"])
		pkgs.remove(pkg["Name"])
		pkg2aurdata[pkg["Name"]] = pkg

	for pkg in pkgs:
		if pacman.find_satisfier_in_syncdbs(pkg):
			repopkgs.append(pkg)
			pkgs.remove(pkg)

	# return aurpkgs, repopkgs, not_found_anywhere_pkgs, aurdata for aurpkgs
	return aurpkgs, repopkgs, pkgs, pkg2aurdata


def install_built_packages(pkgs):
	print("would install now: {}".format(pkgs.join(", ")))


def getchar(msg):
	import tty, termios
	sys.stdout.write(msg)
	sys.stdout.flush()
	fd = sys.stdin.fileno()
	old_settings = termios.tcgetattr(fd)
	try:
		tty.setraw(fd)
		ch = sys.stdin.read(1)
	finally:
		termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
	print()
	return ch


def get_data_dir():
	from xdg import BaseDirectory

	if os.path.isdir(os.path.expanduser('~/.blinky')):  # backward compatibility
		print(" DEPRECATION WARNING: support for ~/.blinky will be removed in future versions, call migrate-blinky-dirs.py to migrate and silence this message")
		return os.path.expanduser('~/.blinky/cache')

	return BaseDirectory.save_data_path('blinky')


def get_cache_dir():
	from xdg import BaseDirectory

	if os.path.isdir(os.path.expanduser('~/.blinky')):  # backward compatibility
		print(" DEPRECATION WARNING: support for ~/.blinky will be removed in future versions, call migrate-blinky-dirs.py to migrate and silence this message")
		return os.path.expanduser('~/.blinky/cache')

	return BaseDirectory.save_cache_path('blinky')
