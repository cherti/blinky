#!/usr/bin/env python3

import subprocess, os

devnull = open(os.devnull, 'w')

is_installed = lambda pkgname: subprocess.call(['pacman', '-Q', pkgname], stdout=devnull, stderr=devnull) == 0
installed_version = lambda pkgname: subprocess.getoutput("pacman -Q {}".format(pkgname)).split()[1]
in_repos = lambda pkgname: subprocess.call(['pacman', '-Si' , pkgname], stdout=devnull, stderr=devnull) == 0

def get_foreign_package_versions():
	pkgs = subprocess.getoutput("pacman -Qm")
	foreign_package_versions = {}
	for p in pkgs.strip().split("\n"):
		name, version = p.split()
		foreign_package_versions[name] = version
	return foreign_package_versions


def install_repo_packets(pkgs, asdeps=True):
	if len(pkgs) > 0:
		cmdlist = ['sudo', 'pacman', '-S']
		if asdeps:
			cmdlist += ['--asdeps']
		cmdlist += [str(p) for p in pkgs]
		print('::', " ".join(cmdlist))
		return subprocess.call(cmdlist)

def install_package_files(pkgs, asdeps):
	if len(pkgs) > 0:
		cmdlist = ['sudo', 'pacman', '-U']
		if asdeps:
			cmdlist += ['--asdeps']
		cmdlist += [str(p) for p in pkgs]
		print('::', " ".join(cmdlist))
		return subprocess.call(cmdlist)

def remove_packets(pkgs):
	if len(pkgs) > 0:
		cmdlist = ['sudo', 'pacman', '-Rsn'] + [str(p) for p in pkgs]
		print('::', " ".join(cmdlist))
		return subprocess.call(cmdlist)
