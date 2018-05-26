#!/usr/bin/env python3

import subprocess, os

devnull = open(os.devnull, 'w')

def is_installed(pkgname):
	r = subprocess.call(['pacman', '-Q', pkgname], stdout=devnull, stderr=devnull)
	return r == 0

def installed_version(pkgname):
	o = subprocess.getoutput("pacman -Q {}".format(pkgname))
	return o.split()[1]

def in_repos(pkgname):
	r = subprocess.call(['pacman', '-Si' , pkgname], stdout=devnull, stderr=devnull)
	return r == 0

def get_foreign_package_versions():
	pkgs = subprocess.getoutput("pacman -Qm")
	foreign_package_versions = {}
	for p in pkgs.strip().split("\n"):
		name, version = p.split()
		foreign_package_versions[name] = version
	return foreign_package_versions

def install_repo_packages(pkgs, asdeps=True):
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

def remove_packages(pkgs):
	if len(pkgs) > 0:
		cmdlist = ['sudo', 'pacman', '-Rsn'] + [str(p) for p in pkgs]
		print('::', " ".join(cmdlist))
		return subprocess.call(cmdlist)
