#!/usr/bin/env python3

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


def install_repo_packets(pkgs, asdeps=True):
	if len(pkgs) > 0:
		cmdlist = ['sudo', 'pacman', '-S']
		if asdeps:
			cmdlist += ['--asdeps']
		cmdlist += [str(p) for p in pkgs]
		print('::', " ".join(cmdlist))
		subprocess.call(cmdlist)


def remove_packets(pkgs):
	if len(pkgs) > 0:
		cmdlist = ['sudo', 'pacman', '-Rsn'] + [str(p) for p in pkgs]
		print('::', " ".join(cmdlist))
		subprocess.call(cmdlist)


def install_built_packages(pkgs):
	print("would install now: {}".format(pkgs.join(", ")))
