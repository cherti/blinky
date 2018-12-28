import requests, subprocess, os, shutil, sys, stat, asyncio, hashlib
from blinky import pacman, utils

# pkg_store holds all packages so that we have all package-objects
# to build the fully interconnected package graph
pkg_store            = {}
srcpkg_store         = {}

# the instantiated-list hold all instantiated packages to fix race
# conditions upon instantiating afterwards by dedup
instantiated_pkgs    = []

def dedup_pkgs(ctx):
	if len(pkg_store) != len(instantiated_pkgs):
		dup_number = len(instantiated_pkgs) - len(pkg_store)
		utils.logmsg(ctx.v, 3, "Deduplicating {} packages".format(dup_number))
		name2obj = {}
		for name, obj in instantiated_pkgs:
			if name in name2obj:
				# we have at least two, let's merge the tree here
				utils.logmsg(ctx.v, 3, "Deduplicating package: {}".format(name))
				name2obj[name].parents += obj.parents
				for p in obj.parents:
					if obj in p.deps:
						p.deps.remove(obj)
						p.deps.append(name2obj[name])
					elif obj in p.makedeps:
						p.makedeps.remove(obj)
						p.makedeps.append(name2obj[name])
			else:
				name2obj[name] = obj


def parse_dep_pkg(pkgname, ctx, parentpkg=None):
	packagename = pkgname.split('>=')[0].split('=')[0]

	if packagename not in pkg_store:
		pkg = Package(packagename, ctx=ctx, firstparent=parentpkg)
		pkg_store[packagename] = pkg
		instantiated_pkgs.append((pkgname, pkg))
	elif parentpkg:
		pkg_store[packagename].parents.append(parentpkg)

	return pkg_store[packagename]


def parse_src_pkg(src_id, version, tarballpath, ctx):
	if src_id in srcpkg_store:
		return srcpkg_store[src_id]
	else:
		srcpkg = SourcePkg(src_id, version, tarballpath, ctx=ctx)
		srcpkg_store[src_id] = srcpkg
		return srcpkg



def pkg_in_cache(pkg):
	pkgs = []
	pkgprefix = '{}-{}-'.format(pkg.name, pkg.version_latest)
	for pkg in os.listdir(pkg.ctx.cachedir):
		if pkgprefix in pkg:
			# was already built at some point
			pkgs.append(pkg)
	return pkgs


class SourcePkg:

	def __init__(self, name, version, tarballpath, ctx=None):
		self.ctx           = ctx
		self.name          = name
		self.version       = version
		self.tarballpath   = 'https://aur.archlinux.org' + tarballpath
		self.tarballname   = tarballpath.split('/')[-1]
		self.reviewed      = False
		self.review_passed = False
		self.built         = False
		self.build_success = False
		self.srcdir        = None
		utils.logmsg(self.ctx.v, 3, "Instantiating source-pkg {}".format(self.name))


	def download(self):
		os.chdir(self.ctx.builddir)
		r = requests.get(self.tarballpath)
		with open(self.tarballname, 'wb') as tarball:
			tarball.write(r.content)

	def extract(self):
		retval = subprocess.call(['tar', '-xzf', self.tarballname])
		if retval != 0:
			utils.logerr(None, "Couldn't extract tarball for {}".format(self.name))

		if os.path.exists(self.tarballname):
			os.remove(self.tarballname)
		self.srcdir = os.path.join(self.ctx.builddir, self.name)




	def build(self, buildflags=[]):
		if self.built:
			return self.build_success

		utils.logmsg(self.ctx.v, 0, "Building package {}".format(self.name))

		os.chdir(self.srcdir)
		self.built = True

		# prepare logfiles
		stdoutlogfile = os.path.join(self.ctx.logdir, "{}-{}.stdout.log".format(self.name, self.version))
		stderrlogfile = os.path.join(self.ctx.logdir, "{}-{}.stderr.log".format(self.name, self.version))

		with open(stdoutlogfile, 'w') as outlog, open(stderrlogfile, 'w') as errlog:
			p = subprocess.Popen(['makepkg'] + buildflags, stdout=outlog, stderr=errlog)
			r = p.wait()

		if r != 0:
			with open(stdoutlogfile, 'a') as outlog, open(stderrlogfile, 'a') as errlog:
				print("\nexit code: {}".format(self.name, r), file=outlog)
				print("\nexit code: {}".format(self.name, r), file=errlog)
			self.build_success = False
			return False
		else:
			self.build_success = True
			return True

	def set_review_state(self, state):
		"""This function is a helper to keep self.review clean and readable"""
		self.review_passed = state
		self.reviewed = True
		return self.review_passed

	def review(self):
		if self.reviewed:
			return self.review_passed

		os.chdir(self.srcdir)

		def save_as_reviewed_file(fname):
			"""
			This function saves the given file in the directory for reviewed files
			of the current package for later comparison.
			"""
			d = os.path.join(self.ctx.revieweddir, self.name)
			os.makedirs(d, exist_ok=True)
			shutil.copyfile(fname, os.path.join(d, fname))

		def hash_file(fname):
			h = hashlib.sha256()
			if os.path.exists(fname):
				with open(fname, 'rb') as f:
					h.update(f.read())

			return h.hexdigest()


		# compare both reference PKGBUILD (if existent) and new PKGBUILD
		refhash = hash_file(os.path.join(self.ctx.revieweddir, self.name, 'PKGBUILD'))
		newhash = hash_file('PKGBUILD')

		if refhash == newhash and not self.ctx.force_review:
			msg = "PKGBUILD of srcpkg {} passed review: already positively reviewed"
			utils.logmsg(self.ctx.v, 3, msg.format(self.name))
		else:
			# we need review
			retval = subprocess.call([os.environ.get('EDITOR') or 'nano', 'PKGBUILD'])
			if 'y' == input('Did PKGBUILD for {} pass review? [y/n] '.format(self.name)).lower():
				save_as_reviewed_file('PKGBUILD')
			else:
				return self.set_review_state(False)


		# compare both reference *.install (if existent) and new *.install
		installfile = '{}.install'.format(self.name)
		if os.path.exists(installfile):

			refhash = hash_file(os.path.join(self.ctx.revieweddir, self.name, installfile))
			newhash = hash_file(installfile)

			if refhash == newhash and not self.ctx.force_review:
				utils.logmsg(self.ctx.v, 3, "{} of srcpkg {} passed review: already positively reviewed".format(installfile, self.name))
			else:
				# we need review
				retval = subprocess.call([os.environ.get('EDITOR') or 'nano', installfile])
				if 'y' == input('Did {} pass review? [y/n] '.format(installfile)).lower():
					save_as_reviewed_file(installfile)
				else:
					return self.set_review_state(False)

		return self.set_review_state(True)

	def cleanup(self):
		if self.srcdir:
			try:
				shutil.rmtree(self.srcdir, onerror=lambda f, p, e: utils.delete_onerror(f, p, e))
			except PermissionError:
				utils.logerr(None, "Cannot remove {}: Permission denied".format(self.srcdir))

			self.srcdir = None  # if we couldn't remove it, we can't next time, so we ignore the exception and continue


class Package:

	def __init__(self, name, ctx=None, firstparent=None, debug=False):
		self.ctx               = ctx
		self.name              = name
		self.installed         = None
		self.version_installed = None
		self.in_repos          = None
		s = pacman.find_local_satisfier(name)
		if s:
			self.installed = True
			self.name = s.name
			self.version_installed = s.version

			if pacman.find_satisfier_in_syncdbs(self.name):
			    self.in_repos = True
		else:
			self.installed = False
			s = pacman.find_satisfier_in_syncdbs(name)
			if s:
				self.in_repos = True
				self.name     = s.name
			else:
				self.in_repos = False

		self.deps              = []
		self.makedeps          = []
		self.optdeps           = []
		self.parents           = [firstparent] if firstparent else []
		self.built_pkgs        = []
		self.srcpkg            = None

		self.rebuild           = False
		if ctx.rebuild == 'tree':
			self.rebuild = True
		elif ctx.rebuild == 'package' and not self.parents:
			self.rebuild = True

		utils.logmsg(self.ctx.v, 3, "Instantiating package {}".format(self.name))

		self.pkgdata = utils.query_aur("info", self.name, single=True)
		self.in_aur = not self.in_repos and self.pkgdata

		utils.logmsg(self.ctx.v, 4, 'Package details: {}; {}; {}; {}'.format(name, "installed" if self.installed else "not installed", "in repos" if self.in_repos else "not in repos", "in AUR" if self.in_aur else "not in AUR"))

		if self.in_aur:
			self.version_latest    = self.pkgdata['Version']


			# concurrently build dependency tree
			loop = asyncio.new_event_loop()

			depnames = [pn.split('>=')[0].split('=')[0] for pn in self.pkgdata.get("Depends") or []]
			makedepnames = [pn.split('>=')[0].split('=')[0] for pn in self.pkgdata.get("MakeDepends") or []]

			async def parse_dependencies(alldeps):
				deps = []
				makedeps = []
				futures = [
					loop.run_in_executor(
						None,
						parse_dep_pkg,
						pname, self.ctx, self
					)
					for pname in alldeps
				]
				for p in await asyncio.gather(*futures):
					if p.name in depnames:
						deps.append(p)
					else:
						makedeps.append(p)

				return deps, makedeps

			try:
				self.deps, self.makedeps = loop.run_until_complete(parse_dependencies(depnames + makedepnames))
			except utils.UnsatisfiableDependencyError as e:
				raise utils.UnsatisfiableDependencyError(str(e) + " for {}".format(self.name))

			if "OptDepends" in self.pkgdata:
				for pkg in self.pkgdata["OptDepends"]:
					self.optdeps.append(pkg)

			self.srcpkg = parse_src_pkg(self.pkgdata["PackageBase"], self.pkgdata["Version"], self.pkgdata["URLPath"], ctx=ctx)

			self.srcpkg.download()
			self.srcpkg.extract()

		elif not self.in_repos and not self.installed:
			# not in AUR, not in repos (not even provided by another package), not installed: well, little we can do...
			raise utils.UnsatisfiableDependencyError("Dependency unsatisfiable via AUR, repos or installed packages: {}".format(self.name))

	def review(self):
		utils.logmsg(self.ctx.v, 3, "reviewing {}".format(self.name))
		for dep in self.deps + self.makedeps:
			if not dep.review():
				return False  # already one dep not passing review is killer, no need to process further

		if self.in_repos:
			utils.logmsg(self.ctx.v, 3, "{} passed review: in_repos".format(self.name))
			return True

		if self.installed and not self.rebuild:
			if not self.in_aur:
				utils.logmsg(self.ctx.v, 3, "{} passed review: installed and not in aur".format(self.name))
				return True
			elif self.version_installed == self.version_latest:
				utils.logmsg(self.ctx.v, 3, "{} passed review: installed in latest version".format(self.name))
				return True

		if self.srcpkg.reviewed:
			utils.logmsg(self.ctx.v, 3, "{} passed review due to positive pre-review".format(self.name))
			return self.srcpkg.review_passed

		if self.in_aur and len(pkg_in_cache(self)) > 0 and not self.rebuild:
			utils.logmsg(self.ctx.v, 3, "{} passed review: in cache".format(self.name))
			return True

		return self.srcpkg.review()

	def build(self, buildflags=['-Cdf'], recursive=False):
		if recursive:
			for d in self.deps:
				succeeded = d.build(buildflags=buildflags, recursive=True)
				if not succeeded:
					return False  # one dep fails, the entire branch fails immediately, software will not be runnable

		if self.in_repos or (self.installed and not self.in_aur):
			return True

		if self.installed and self.in_aur and self.version_installed == self.version_latest and not self.rebuild:
			return True

		pkgs = pkg_in_cache(self)
		if len(pkgs) > 0 and not self.rebuild:
			self.built_pkgs.append(pkgs[0]) # we only need one of them, not all, if multiple ones with different extensions have been built
			return True

		utils.logmsg(self.ctx.v, 3, "building sources of {}".format(self.name))
		if self.srcpkg.built:
			return self.srcpkg.build_success

		succeeded = self.srcpkg.build(buildflags=buildflags)
		if not succeeded:
			utils.logerr(None, "Building sources of package {} failed, aborting this subtree".format(self.name))
			return False

		pkgext = os.environ.get('PKGEXT') or 'tar.xz'
		fullpkgnames = []
		fullpkgname_x86_64_tmpl = "{}-{}-x86_64.pkg.{}"
		fullpkgname_any_tmpl = "{}-{}-any.pkg.{}"
		if fullpkgname_x86_64_tmpl.format(self.name, self.version_latest, pkgext) in os.listdir(self.srcpkg.srcdir):
			fullpkgnames.append(fullpkgname_x86_64_tmpl.format(self.name, self.version_latest, pkgext))
		elif fullpkgname_any_tmpl.format(self.name, self.version_latest, pkgext) in os.listdir(self.srcpkg.srcdir):
			fullpkgnames.append(fullpkgname_any_tmpl.format(self.name, self.version_latest, pkgext))
		else:
			fullpkgnames = [p for p in os.listdir(self.srcpkg.srcdir) if p.endswith('.pkg.{}'.format(pkgext))]

		if fullpkgnames:
			for fpn in fullpkgnames:
				self.built_pkgs.append(fpn)
				if os.path.exists(os.path.join(self.ctx.cachedir, fpn)):
					if not os.path.isfile(os.path.join(self.ctx.cachedir, fpn)):
						utils.logerr(None, 0, "Something (that's not a file) is shadowing package {} in cache directory {}".format((fpn), self.cachedir))
				else:
					shutil.move(os.path.join(self.srcpkg.srcdir, fpn), self.ctx.cachedir)
		else:
			utils.logerr(None, "No package file found in builddir for {}, aborting this subtree".format(self.name))
			return False

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

	def get_optdeps(self):
		optdeps = []
		for d in self.deps:
			od = d.get_optdeps()
			if len(od) > 0:
				optdeps += od

		if len(self.optdeps) > 0:
			optdeps.append((self.name, self.optdeps))

		return optdeps

	def remove_sources(self, recursive=True):
		if self.srcpkg:
			self.srcpkg.cleanup()

		if recursive:
			for d in self.deps + self.makedeps:
				d.remove_sources()



	def __str__(self):
		return self.name

	def __repr__(self):
		return str(self)

