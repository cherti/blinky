import requests, subprocess, os, shutil

# packet_store holds all packets so that we have all packet-objects
# to build the fully interconnected packet graph
packet_store = {}

built_packets = []
repo_deps = []

makedepends = []
in_repo_depends = []

devnull = open(os.devnull, 'w')

localaurpath=os.path.expanduser('~/.aur')
cachedir = os.path.join(localaurpath, 'cache')
builddir = os.path.join(localaurpath, 'build')
os.makedirs(localaurpath, exist_ok=True)
os.makedirs(cachedir, exist_ok=True)
os.makedirs(builddir, exist_ok=True)

is_installed = lambda pkgname: subprocess.call(['pacman', '-Q', pkgname], stdout=devnull, stderr=devnull) == 0
installed_version = lambda pkgname: subprocess.getoutput("pacman -Q {}".format(pkgname)).split()[1]
in_repos = lambda pkgname: subprocess.call(['pacman', '-Si' , pkgname], stdout=devnull, stderr=devnull) == 0

def parse_dep_pkg(pkgname, parentpkg=None):
	packetname = pkgname.split('>=')[0]

	if packetname not in packet_store:
		packet_store[packetname] = Packet(packetname, firstparent=parentpkg)
	elif parentpkg:
		packet_store[packetname].parents.append(parentpkg)

	return packet_store[packetname]

class Packet:

	def __init__(self, name, firstparent=None):
		print('instantate', name)
		self.name      = name
		self.installed = is_installed(name)
		self.deps      = []
		self.makedeps  = []
		self.parents   = [firstparent] if firstparent else []

		r = requests.get("https://aur.archlinux.org/rpc/", params={"type": "info", "v":5, "arg":name})
		aurdata = r.json()
		assert aurdata["resultcount"] <= 1

		self.version_installed = installed_version(name) if self.installed else None
		self.in_repos = in_repos(name)
		self.in_aur = not self.in_repos and aurdata['resultcount'] == 1 if self.installed else aurdata['resultcount'] > 0

		if self.in_aur:
			pkgdata = aurdata["results"][0]  # we can do [0] because aurdata should only ever have one element/packet

			if "Depends" in pkgdata:
				for pkg in pkgdata["Depends"]:
					self.deps.append(parse_dep_pkg(pkg))

			if "MakeDepends" in pkgdata:
				for pkg in pkgdata["MakeDepends"]:
					self.makedeps.append(parse_dep_pkg(pkg))

			self.tarballpath = 'https://aur.archlinux.org' + pkgdata['URLPath']
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

	def build(self, buildflags=['-C', '-d']):
		if self in built_packets:
			# was already built, most likely as dependency of another packet in the graph
			return

		os.chdir(os.path.join(builddir, self.name))
		subprocess.call(['makepkg'] + buildflags)
		packetname = '{}.tar.xz'.format(self.name)
		built_packets.append(packetname)
		shutil.move(packetname, cachedir)

		for d in self.deps:
			d.build(buildflags)

	def get_repodeps():
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

	def get_makedeps():
		if self.in_repos:
			return set()
		else:
			makedeps = set()
			for d in self.deps:
				makedeps.union(d.get_makedeps())


def install_repo_packets(pkgs):
	cmdlist = ['sudo', 'pacman', '-S'] + pkgs
	print('::', " ".join(cmdlist))
	subprocess.call(cmdlist)


def remove_packets(pkgs):
	cmdlist = ['sudo', 'pacman', '-Rsn'] + pkgs
	print('::', " ".join(cmdlist))
	subprocess.call(cmdlist)
