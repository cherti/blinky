import requests, subprocess

# packet_store holds all packets so that we have all packet-objects
# to build the fully interconnected packet graph
packet_store = {}

class Packet:

	def __init__(self, name):
		self.name = name
		self.installed = subprocess.call(['pacman', '-Q', name]) == 0

		r = requests.get("https://aur.archlinux.org/rpc/", params={"type": "info", "v":5, "arg":name})

		assert result["resultcount"] <= 1

		result = r.json()


		if self.installed:
			self.version_installed = subprocess.call('pacman -Q {}'.format(name))
			self.in_repos = subprocess.call(['pacman', '-Qn', name]) == 0
			self.in_aur = subprocess.call(['pacman', '-Qn', name])
		else:
			self.in_repos = subprocess.call(['pacman', '-Ss' , '^{}$'.format(name)]) == 0
			self.in_aur == result['resultcount'] > 0


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
