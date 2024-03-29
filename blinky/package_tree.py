import requests, subprocess, os, shutil, sys, stat, asyncio, hashlib, concurrent
from termcolor import colored
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


def parse_dep_pkg(pkgname, ctx, parentpkg=None, aurdata=None):
	packagename = pkgname.split('>=')[0].split('=')[0]

	if packagename not in pkg_store:
		pkg = Package(packagename, ctx=ctx, firstparent=parentpkg, aurdata=aurdata)
		pkg_store[packagename] = pkg
		instantiated_pkgs.append((pkgname, pkg))
	elif parentpkg:
		pkg_store[packagename].parents.append(parentpkg)

	return pkg_store[packagename]


def parse_src_pkg(src_id, version, tarballpath, ctx):
	if src_id not in srcpkg_store:
		srcpkg_store[src_id] = SourcePkg(src_id, version, tarballpath, ctx=ctx)


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
		self.downloaded    = False
		self.built         = False
		self.build_success = False
		self.srcdir        = None
		self.stdoutlogfile = os.path.join(self.ctx.logdir, "{}-{}.stdout.log".format(self.name, self.version))
		self.stderrlogfile = os.path.join(self.ctx.logdir, "{}-{}.stderr.log".format(self.name, self.version))
		utils.logmsg(self.ctx.v, 3, "Instantiating source-pkg {}".format(self.name))


	def get(self):
		if not self.downloaded:
			self.downloaded = True

			# download
			os.chdir(self.ctx.builddir)
			r = requests.get(self.tarballpath)
			with open(self.tarballname, 'wb') as tarball:
				tarball.write(r.content)

			# extract
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

		with open(self.stdoutlogfile, 'w') as outlog, open(self.stderrlogfile, 'w') as errlog:
			p = subprocess.Popen(['makepkg'] + buildflags, stdout=outlog, stderr=errlog)
			r = p.wait()

		if r != 0:
			with open(self.stdoutlogfile, 'a') as outlog, open(self.stderrlogfile, 'a') as errlog:
				print("\nexit code: {}".format(r), file=outlog)
				print("\nexit code: {}".format(r), file=errlog)
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

	def review(self, via=None):
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

		def review_file(fname, via=None):
			ref_file = os.path.join(self.ctx.revieweddir, self.name, fname)
			# compare both reference PKGBUILD (if existent) and new PKGBUILD

			refhash = hash_file(ref_file)
			newhash = hash_file(fname)

			if refhash == newhash and not self.ctx.force_review:
				msg = "{} of srcpkg {} passed review: already positively reviewed previously"
				utils.logmsg(self.ctx.v, 0, msg.format(fname, self.name))
				return True
			else:
				# we need review, first diff it if reference exists
				user_verdict = None
				if os.path.exists(ref_file):
					user_verdict = 'd'  # diff
				else:
					user_verdict = 'e'  # edit (display with direct editing option)

				while True:
					if user_verdict == 'p':  # file passed review
						save_as_reviewed_file(fname)
						return True
					elif user_verdict in ['f', 's']:  # file failed review or was skipped
						return False
					elif user_verdict == 'e':  # user decides to edit
						subprocess.call([os.environ.get('EDITOR') or 'nano', fname])
					elif user_verdict == 'd':  # user decides to diff
						if os.path.exists(ref_file):

							termsize = shutil.get_terminal_size()
							separator_width = termsize.columns - 2  # 1 whitespace padding on each side

							print()
							print(colored(' ' + '='*separator_width, attrs=['bold']))
							print()
							if self.ctx.difftool:
								try:
									subprocess.call([self.ctx.difftool, fname, ref_file])
								except Exception as e:
									utils.logerr(4, "Error using {} for diff: {}".format(self.ctx.difftool, e))
							else:
								with open(fname, 'r') as f:
									max_linelength = max([len(line) for line in f.read().strip().split('\n')])

								diffwidth = min(2*max_linelength, os.get_terminal_size().columns)
								diffcmd = ["colordiff", "--side-by-side", "--left-column", "--width={}".format(diffwidth)]

								subprocess.call(diffcmd + [fname, ref_file])
								print()

								padding = " "*(int(diffwidth/2)-9)
								subscript = "{}new <== | ==> previously positively reviewed".format(padding)
								print(colored(subscript, attrs=['bold']))

						else:
							utils.logmsg(0, 0, "No reference available, cannot provide diff")

					if via:
						# if we get a source pkg calling the review we can deduct
						# a dependency chain leading to this srcpkg
						origin = ""
						if via.name != self.name:
							# if the SourcePkg and the Package are named identically, hide the SourcePkg-distinction
							origin += "via " + via.name

						while via.parents:
							origin += " → " + via.parents[0].name
							if len(via.parents) > 1:
								origin += " (among others)"
							via = via.parents[0]

						if origin == "":
							print("{} of package {}:".format(fname, self.name))
						else:
							print("{} of package {} ({}):".format(fname, self.name, origin))
					else:
						print("{} of package {}:".format(fname, self.name))

					user_verdict = utils.getchar("(P)ass review, (F)ail review, (E)dit, (D)iff, (S)kip?: [p/f/e/d/s] ").lower()


		positively_reviewed = review_file('PKGBUILD', via=via)
		if not positively_reviewed:
			return self.set_review_state(False)

		installfiles = [f for f in os.listdir() if f.endswith('.install')]
		for installfile in installfiles:
			if os.path.exists(installfile):
				positively_reviewed = review_file(installfile, via=via)
				if not positively_reviewed:
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

	def __init__(self, name, ctx=None, firstparent=None, aurdata=None, debug=False):
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

		# we can be this straight and directly raise here as all explicitly specified packages
		# in the ignorelist should have already been dropped here
		if not self.installed and self.name in ctx.ignored_pkgs:
			raise utils.UnsatisfiableDependencyError("Dependency unsatisfiable: ignored package: {}".format(self.name))

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

		self.pkgdata = None
		if aurdata:
			self.pkgdata = aurdata
		else:
			try:
				self.pkgdata = utils.query_aur("info", self.name, single=True, ignore_ood=ctx.ignore_ood)
			except utils.APIError as e:

				msg = "Dependency unsatisfiable via AUR, repos or installed packages: {}"
				if e.type == 'ratelimit':
					msg = "Dependency unsatisfiable due to rate limit on AUR-API, try again tomorrow: {}"
				elif e.type == 'unavailable':
					msg = "Dependency unsatisfiable due to unavailability of AUR-API, try again later: {}"

				raise utils.UnsatisfiableDependencyError(msg.format(self.name))

		self.in_aur = not self.in_repos and self.pkgdata

		utils.logmsg(self.ctx.v, 4, 'Package details: {}; {}; {}; {}'.format(name, "installed" if self.installed else "not installed", "in repos" if self.in_repos else "not in repos", "in AUR" if self.in_aur else "not in AUR"))

		if self.in_aur:
			self.version_latest    = self.pkgdata['Version']

			depnames = [pn.split('>=')[0].split('=')[0] for pn in self.pkgdata.get("Depends") or []]
			makedepnames  = [pn.split('>=')[0].split('=')[0] for pn in self.pkgdata.get("MakeDepends") or []]
			makedepnames += [pn.split('>=')[0].split('=')[0] for pn in self.pkgdata.get("CheckDepends") or []]

			_, _, _, aurdata = utils.check_in_aur(depnames + makedepnames)

			try:
				with concurrent.futures.ThreadPoolExecutor(max_workers=10) as e:
					dep_pkgs_parser, makedep_pkgs_parser = [], []
					for depname in depnames:
						aurpkgdata = aurdata[depname] if depname in aurdata else None
						dep_pkgs_parser.append(e.submit(parse_dep_pkg, depname, self.ctx, self, aurpkgdata))

					for makedepname in makedepnames:
						aurpkgdata = aurdata[makedepname] if makedepname in aurdata else None
						makedep_pkgs_parser.append(e.submit(parse_dep_pkg, makedepname, self.ctx, self, aurpkgdata))

					self.deps = [p.result() for p in dep_pkgs_parser]
					self.makedeps = [p.result() for p in makedep_pkgs_parser]
			except utils.UnsatisfiableDependencyError as e:
				raise utils.UnsatisfiableDependencyError(str(e) + " for {}".format(self.name))
			except Exception as e:
				raise e

			if "OptDepends" in self.pkgdata:
				for pkg in self.pkgdata["OptDepends"]:
					self.optdeps.append(pkg)

			parse_src_pkg(self.pkgdata["PackageBase"], self.pkgdata["Version"], self.pkgdata["URLPath"], ctx=ctx)


		elif not self.in_repos and not self.installed:
			# not in AUR, not in repos (not even provided by another package), not installed: well, little we can do...
			raise utils.UnsatisfiableDependencyError("Dependency unsatisfiable via AUR, repos or installed packages: {}".format(self.name))


	def get_src(self):
		if self.in_aur:
			self.srcpkg = srcpkg_store[self.pkgdata["PackageBase"]]
			self.srcpkg.get()

		e = concurrent.futures.ThreadPoolExecutor(max_workers=10)
		for d in self.deps + self.makedeps:
			e.submit(d.get_src)
		e.shutdown(wait=True)


	def review(self):
		utils.logmsg(self.ctx.v, 3, "reviewing {}".format(self.name))

		for dep in self.deps + self.makedeps:  # same as above + checking for repo-makedeps
			if not dep.review():
				utils.logmsg(self.ctx.v, 3, "{} failed review: dependency failed review".format(self.name))
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

		return self.srcpkg.review(via=self)


	def build(self, buildflags=['-Cdf'], recursive=False, dependency=False):

		if dependency and self.installed:
			# if this is a dependency and already installed, we do not bother,
			# upgrades are taken care of by -Syu, just as it is common with the official repos
			utils.logmsg(self.ctx.v, 3, "skipping build of installed dependency {}".format(self.name))
			return True

		if not self.check_makedeps_installed():
			msg = "Makedeps not installed for {}".format(self.name)
			utils.logerr(None, "{}, aborting this subtree".format(msg))
			return False

		if recursive:
			for d in self.deps:
				succeeded = d.build(buildflags=buildflags, recursive=True, dependency=True)
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
		succeeded = self.srcpkg.build(buildflags=buildflags)
		if not succeeded:
			utils.logerr(None, "Building sources of package {} failed, aborting this subtree".format(self.name))
			utils.logerr(None, "├─stdout-log: {}".format(self.srcpkg.stdoutlogfile), primary=False)
			utils.logerr(None, "└─stderr-log: {}".format(self.srcpkg.stderrlogfile), primary=False)
			if self.ctx.printed_error_log_lines > 0:
				utils.logmsg(self.ctx.v, 0, "Tail of stderr:")
				with open(self.srcpkg.stderrlogfile, 'r') as logfile:
					errorlog = logfile.read().strip().split("\n")
					for line in errorlog[-self.ctx.printed_error_log_lines:]:
						print("    {}".format(line))
			if self.ctx.printed_error_log_lines == -1:
				utils.logmsg(self.ctx.v, 0, "stderr:")
				with open(self.srcpkg.stderrlogfile, 'r') as logfile:
					errorlog = logfile.read().strip().split("\n")
					for line in errorlog:
						print("    {}".format(line))

			return False

		pkgext_makepkgconf = subprocess.getoutput("bash -c 'source {} && echo $PKGEXT'".format(self.ctx.makepkgconf))
		pkgext_env = os.environ.get('PKGEXT')

		pkgext = pkgext_env or pkgext_makepkgconf or '.pkg.tar.xz'
		fullpkgnames = []
		fullpkgname_x86_64_tmpl = "{}-{}-x86_64{}"
		fullpkgname_any_tmpl = "{}-{}-any{}"
		if fullpkgname_x86_64_tmpl.format(self.name, self.version_latest, pkgext) in os.listdir(self.srcpkg.srcdir):
			fullpkgnames.append(fullpkgname_x86_64_tmpl.format(self.name, self.version_latest, pkgext))
		elif fullpkgname_any_tmpl.format(self.name, self.version_latest, pkgext) in os.listdir(self.srcpkg.srcdir):
			fullpkgnames.append(fullpkgname_any_tmpl.format(self.name, self.version_latest, pkgext))
		else:
			fullpkgnames = [p for p in os.listdir(self.srcpkg.srcdir) if p.endswith(pkgext)]

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

	def get_deps(self):
		if self.in_repos:
			return set()  # pacman will take care of repodep-tree
		else:
			deps = set(self.deps)
			for d in self.deps:
				deps.union(d.get_deps())
			return deps

	def get_makedeps(self):
		if self.in_repos:
			return set()
		else:
			makedeps = set(self.makedeps)
			for d in self.deps:
				makedeps.union(d.get_makedeps())
			return makedeps

	def check_makedeps_installed(self):
		md = self.get_makedeps()
		for m in md:
		# for every makedep...
			if not m.installed:
			# ...if it has not been installed anyways...
				if not pacman.find_local_satisfier(m.name):
					# ...check if it is installed now...
					return False  # ...otherwise return failure

		return True

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

