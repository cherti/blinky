#!/usr/bin/env python3

import subprocess, os, pyalpm, pycman
from distutils import spawn
from threading import Lock

handle = pycman.config.init_with_config('/etc/pacman.conf') #pyalpm.Handle("/", "/var/lib/pacman")
ldb_lock, ldb = Lock(), handle.get_localdb()
sdbs = [(Lock(), sdb) for sdb in handle.get_syncdbs()]

devnull = open(os.devnull, 'w')
sudo = spawn.find_executable("sudo")

def refresh():
	global handle, ldb, sdbs
	handle = pycman.config.init_with_config('/etc/pacman.conf') #pyalpm.Handle("/", "/var/lib/pacman")
	ldb, sdbs = handle.get_localdb(), [(Lock(), sdb) for sdb in handle.get_syncdbs()]

def execute_privileged(cmdlist):
	if sudo:
		return subprocess.call(["sudo"] + cmdlist)
	else:
		return subprocess.call(["su", "-c"] + [" ".join(cmdlist)])

def find_local_satisfier(pkgname):
	ldb_lock.acquire()
	try:
		satisfier = pyalpm.find_satisfier(ldb.pkgcache, pkgname)
	finally:
		ldb_lock.release()

	return satisfier

def find_satisfier_in_syncdbs(pkgname):
	for lock, db in sdbs:
		lock.acquire()
		try:
			s = pyalpm.find_satisfier(db.pkgcache, pkgname)
		finally:
			lock.release()

		if s:
			return s

	return None


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

		ret = execute_privileged(cmdlist)
		refresh()
		return ret == 0

def install_package_files(pkgs, asdeps):
	if len(pkgs) > 0:
		cmdlist = ['pacman', '-U']
		if asdeps:
			cmdlist += ['--asdeps']
		cmdlist += [str(p) for p in pkgs]

		ret = execute_privileged(cmdlist)
		refresh()
		return ret == 0

def remove_packages(pkgs):
	if len(pkgs) > 0:
		cmdlist = ['pacman', '-Rsn'] + [str(p) for p in pkgs]

		ret = execute_privileged(cmdlist)
		refresh()
		return ret == 0
