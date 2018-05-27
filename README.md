# Blinky

blinky is an AUR-helper that is intended to complement the package manager `pacman` in Archlinux.
It supports searching for, installing and upgrading packages from the AUR.


## Core Principles

The principles that blinky is based upon are the following:

  * **Require minimal user interaction:** All files to be reviewed (PKGBUILD, install-files) are presented for review directly at the beginning, afterwards everything is built in one go with no further user interaction necessary; as soon as it is clear that one package of this subtree did not pass review, blinky stops asking for reviews of a subtree of the dependency graph 
  * **Build as much as possible:** if some packages fail review, blinky still builds and installs all subtrees of the dependency-graph that still fully passed review
  * **Do not mix AUR and repos:** Both are very different in their concept, therefore AUR and repos should not be mixed, for the repos we already have `pacman`, no need to reimplement it
  * **Be as close to pacman's CLI-interface as possible:** blinky uses the very same flags as pacman wherever possible, because tooling should be consistent
  * **Be clean:** Dependencies from AUR will be installed with the dependency-flag set, makedepends will be removed after building if they haven't been installed previously; blinky is drop-in software and migrating away from blinky is easily possible as it does not save any relevant state outside of the ArchLinux package management system.


## State

blinky is currently in the bug squashing phase before release. If you want to help testing it, this is very appreciated. Just clone this repository and checkout the testing-branch. Its readme includes all relevant information how to run blinky.
