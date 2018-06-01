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

blinky is currently in the bug squashing phase before its first release. If you want to help testing it, this as well as gerneral feedback is very appreciated!


## Running blinky (e.g. for testing or seeing if it suits your needs)

To test, it is recommended to just clone this repository and run blinky right out of it as outlined below.

## Dependencies

All dependencies are present in the official ArchLinux package repositories, they are:

  * `python-requests`
  * `pyalpm`
  * `python-termcolor`

## How to use it

Just run blinky right out of the cloned directory; `python blinky.py --help` should give all relevant information you need.

In particular the currently available options are

  * package installation: `python blinky.py -S <package> [<package> ...]`
  * package search: `python blinky.py -Ss <package> [<package> ...]`
  * detailed package info: `python blinky.py -Si <package> [<package> ...]`
  * package updates: `python blinky.py -Syu`

Blinky will create a folder defaulting to `~/.blinky` where it builds stuff and stores built packgages.

