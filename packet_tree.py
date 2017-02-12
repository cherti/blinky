import requests, subprocess, os

# packet_store holds all packets so that we have all packet-objects
# to build the fully interconnected packet graph
packet_store = {}

makedepends = []

devnull = open(os.devnull, 'w')

localaurpath=os.path.expanduser('~/.aur')

def is_installed(pkgname):
	return subprocess.call(['pacman', '-Q', pkgname], stdout=devnull, stderr=devnull) == 0

class Packet:

	def __init__(self, name):
		print('instantate', name)
		self.name = name
		self.installed = is_installed(pkgname)

		r = requests.get("https://aur.archlinux.org/rpc/", params={"type": "info", "v":5, "arg":name})
		result = r.json()

		assert result["resultcount"] <= 1

		if self.installed:
			self.version_installed = subprocess.getoutput("pacman -Q {}".format(name)).split()[1]
			self.in_repos = subprocess.call(['pacman', '-Qn', name], stdout=devnull, stderr=devnull) == 0
			self.in_aur = not self.in_repos and result['resultcount'] == 1
		else:
			self.in_repos = subprocess.call(['pacman', '-Ss' , '^{}$'.format(name)], stdout=devnull, stderr=devnull) == 0
			self.in_aur = result['resultcount'] > 0

		if self.in_aur:
			pkgdata = result["results"][0]  # we can do [0] because info should only ever have one result

			self.deps = []
			if "Depends" in pkgdata:
				for pkg in pkgdata["Depends"]:
					if '>=' in pkg:
						packetname = pkg.split('>=')[0]
					else:
						packetname = pkg

					if packetname not in packet_store:
						packet_store[packetname] = Packet(packetname)

					self.deps.append(packet_store[packetname])

			for makedep in pkgdata['MakeDepends']:
				log_makedepends(makedep)

			self.tarballpath = 'https://aur.archlinux.org' + pkgdata['URLPath']
			self.tarballname = self.tarballpath.split('/')[-1]

			self.download()
			self.extract()

	def download(self):
		os.chdir(localaurpath)
		r = requests.get(self.tarballpath)
		with open(self.tarballname, 'wb') as tarball:
			tarball.write(r.content)

	def extract(self):
		subprocess.call(['tar', '-xzf', self.tarballname])
		os.remove(self.tarballname)

	def review(self):
		pass

	def build(self):
		pass


def log_makedepends(dep):
	if not is_installed(dep):
		makedepends.append(makedep)


def install_makedepends():
	"""
	install all makedepends that are not installed yet
	"""
	cmdlist = ['sudo', 'pacman', '-S'] + makedepends
	print('::', " ".join(cmdlist))
	subprocess.call(['sudo', 'pacman', '-S'] + makedepends)


def remove_makedepends():
	"""
	remove all makedepends, that have previously been uninstalled
	"""
	cmdlist = ['sudo', 'pacman', '-Rsn'] + makedepends
	print('::', " ".join(cmdlist))
	subprocess.call(['sudo', 'pacman', '-Rsn'] + makedepends)
