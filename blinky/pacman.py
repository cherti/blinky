#!/usr/bin/env python3

import subprocess, os, pyalpm
from distutils import spawn

handle = pyalpm.Handle("/", "/var/lib/pacman")
ldb = handle.get_localdb()
sdb = handle.get_syncdbs()

devnull = open(os.devnull, 'w')
sudo = spawn.find_executable("sudo")

def execute_privileged(cmdlist):
	if sudo:
		return subprocess.call(["sudo"] + cmdlist)
	else:
		return subprocess.call(["su", "-c"] + [" ".join(cmdlist)])

def is_installed(pkgname):
	return pyalpm.find_satisfier(ldb.pkgcache, pkgname)

def installed_version(pkgname):
	s = pyalpm.find_satisfier(ldb.pkgcache, pkgname)
	return s.version

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
		cmdlist = ['pacman', '-S']
		if asdeps:
			cmdlist += ['--asdeps']
		cmdlist += [str(p) for p in pkgs]
		return execute_privileged(cmdlist) == 0

def install_package_files(pkgs, asdeps):
	if len(pkgs) > 0:
		cmdlist = ['pacman', '-U']
		if asdeps:
			cmdlist += ['--asdeps']
		cmdlist += [str(p) for p in pkgs]
		return execute_privileged(cmdlist) == 0

def remove_packages(pkgs):
	if len(pkgs) > 0:
		cmdlist = ['pacman', '-Rsn'] + [str(p) for p in pkgs]
		return execute_privileged(cmdlist) == 0
