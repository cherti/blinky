import requests, subprocess, os, shutil, sys
import utils
from pacman import is_installed, installed_version, in_repos

# pkg_store holds all packages so that we have all package-objects
# to build the fully interconnected package graph
pkg_store = {}

devnull = open(os.devnull, 'w')

#localaurpath=os.path.expanduser('~/.aur')
localaurpath=os.path.abspath(os.path.expanduser('aur'))
cachedir = os.path.abspath(os.path.join(localaurpath, 'cache'))
builddir = os.path.abspath(os.path.join(localaurpath, 'build'))
os.makedirs(localaurpath, exist_ok=True)
os.makedirs(cachedir, exist_ok=True)
os.makedirs(builddir, exist_ok=True)


def parse_dep_pkg(pkgname, parentpkg=None):
	packagename = pkgname.split('>=')[0]

	if packagename not in pkg_store:
		pkg_store[packagename] = Package(packagename, firstparent=parentpkg)
	elif parentpkg:
		pkg_store[packagename].parents.append(parentpkg)

	return pkg_store[packagename]


def pkg_in_cache(pkg):
	pkgs = []
	pkgprefix = '{}-{}-x86_64.pkg'.format(pkg.name, pkg.version_latest)
	for pkg in os.listdir(cachedir):
		if pkgprefix in pkg:
			# was already built at some point
			pkgs.append(pkg)
	return pkgs



class Package:

	def __init__(self, name, firstparent=None, debug=False, ctx=None):
		self.name       = name
		self.installed  = is_installed(name)
		self.deps       = []
		self.makedeps   = []
		self.parents    = [firstparent] if firstparent else []
		self.built_pkgs = []
		self.version_installed = installed_version(name) if self.installed else None
		self.in_repos = in_repos(name)

		self.pkgdata = utils.query_aur("info", self.name, single=True)
		self.in_aur = not self.in_repos and self.pkgdata

		if debug: print('instantate {}; {}; {}'.format(name, "installed" if self.installed else "not installed", "in repos" if self.in_repos else "not in repos"))

		if self.in_aur:
			self.pkgdata = aurdata["results"][0]  # we can do [0] because aurdata should only ever have one element/package
			self.version_latest    = self.pkgdata['Version']

			if "Depends" in self.pkgdata:
				for pkg in self.pkgdata["Depends"]:
					self.deps.append(parse_dep_pkg(pkg))

			if "MakeDepends" in self.pkgdata:
				for pkg in self.pkgdata["MakeDepends"]:
					self.makedeps.append(parse_dep_pkg(pkg))

			self.tarballpath = 'https://aur.archlinux.org' + self.pkgdata['URLPath']
			self.tarballname = self.tarballpath.split('/')[-1]

			self.download()
			self.extract()

	def download(self):
		os.chdir(builddir)
		r = requests.get(self.tarballpath)
		with open(self.tarballname, 'wb') as tarball:
			tarball.write(r.content)

	def extract(self):
		subprocess.call(['tar', '-xzf', self.tarballname])
		os.remove(self.tarballname)

	def review(self):
		if self.in_repos:
			return True

		if len(pkg_in_cache(self)) > 0:
			return True

		retval = subprocess.call([os.environ.get('EDITOR') or 'nano', self.name + '/PKGBUILD'])
		if 'y' != input('Did PKGBUILD pass review? [y/n] ').lower():
			return False

		if os.path.exists('{n}/{n}.install'.format(n=self.name)):
			retval = subprocess.call([os.environ.get('EDITOR') or 'nano', '{n}/{n}.install'.format(n=self.name)])
			if 'y' != input('Did {}.install pass review? [y/n] '.format(self.name)).lower():
				return False

		for dep in self.deps + self.makedeps:
			if not dep.review():
				return False  # already one dep not passing review is killer, no need to process further

		return True

	def build(self, buildflags=['-C', '-d'], recursive=False):
		pkgs = pkg_in_cache(self)
		if len(pkgs) > 0:
			self.built_pkgs += pkgs[0]
			return True

		os.chdir(os.path.join(builddir, self.name))
		r = subprocess.call(['makepkg'] + buildflags)
		if r != 0:
			print(":: makepkg for package {} terminated with exit code {}, aborting this subpath".format(self.name, r), file=sys.stderr)
			return False
		else:
			pkgext = os.environ.get('PKGEXT') or 'tar.xz'
			pkgs = [f for f in os.listdir() if f.endswith('x86_64.pkg.'+pkgext) and not os.path.isdir(f)]
			for pkgname in pkgs:
				self.built_pkgs.append(pkgname)
				shutil.move(pkgname, cachedir)

			if recursive:
				for d in self.deps:
					succeded = d.build(buildflags=buildflags, recursive=True)
					if not succeded:
						return False  # one dep fails, the entire branch fails immediately, software will not be runnable

			return True

	def get_repodeps(self):
		if self.in_repos:
			return set()  # pacman will take care of repodep-tree
		else:
			rdeps = set()
			for d in self.deps:
				if d.in_repos:
					rdeps.add(d)
				else:
					rdeps.union(d.get_repodeps())
			return rdeps

	def get_makedeps(self):
		if self.in_repos:
			return set()
		else:
			makedeps = set(self.makedeps)
			for d in self.deps:
				makedeps.union(d.get_makedeps())
			return makedeps

	def get_built_pkgs(self):
		pkgs = set(self.built_pkgs)
		for d in self.deps:
			pkgs.union(d.get_built_pkgs())
		return pkgs

	def __str__(self):
		return self.name

	def __repr__(self):
		return str(self)

