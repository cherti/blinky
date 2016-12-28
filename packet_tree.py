import requests, subprocess, os

# packet_store holds all packets so that we have all packet-objects
# to build the fully interconnected packet graph
packet_store = {}
devnull = open(os.devnull, 'w')

class Packet:

	def __init__(self, name):
		print('instantate', name)
		self.name = name
		self.installed = subprocess.call(['pacman', '-Q', name], stdout=devnull, stderr=devnull) == 0

		r = requests.get("https://aur.archlinux.org/rpc/", params={"type": "info", "v":5, "arg":name})
		result = r.json()

		assert result["resultcount"] <= 1


		if self.installed:
			self.version_installed = subprocess.call(['pacman', '-Q', name], stdout=devnull, stderr=devnull)
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
