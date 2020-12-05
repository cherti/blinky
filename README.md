# Blinky

blinky is an AUR-helper that is intended to complement the package manager `pacman` in Archlinux.
It supports searching for, installing and upgrading packages from the AUR and is especially built for making upgrades of AUR-packages as painless as possible.

## Core Principles

The principles that blinky is based upon are the following:

  * **Require minimal user interaction:** All files to be reviewed (PKGBUILD, install-files) are presented for review directly at the beginning, afterwards everything is built in one go with no further user interaction necessary; as soon as it is clear that one package of this subtree did not pass review, blinky stops asking for reviews of a subtree of the dependency graph 
  * **Build as much as possible:** if some packages fail review, blinky still builds and installs all subtrees of the dependency-graph that still fully passed review
  * **Do not mix AUR and repos:** Both are very different in their concept, therefore AUR and repos should not be mixed, for the repos we already have `pacman`, no need to reimplement it
  * **Be as close to pacman's CLI-interface as possible:** blinky uses the very same flags as pacman wherever possible, because tooling should be consistent
  * **Be clean:** Dependencies from AUR will be installed with the dependency-flag set, makedepends will be removed after building if they haven't been installed previously; blinky is drop-in software and migrating away from blinky is easily possible as it does not save any relevant state outside of the ArchLinux package management system.


## How to get it

Just install [this package](https://aur.archlinux.org/packages/blinky) from AUR.

## How to use it

In particular the currently available options are

  * package installation: `blinky -S <package> [<package> ...]`
  * package search: `blinky -Ss <package> [<package> ...]`
  * detailed package info: `blinky -Si <package> [<package> ...]`
  * package updates: `blinky -Syu`
  * clean cache: `blinky -Sc` or `blinky -Scc`
  * explicitly rebuild packages: `blinky -Sr [<package> ...]` or `blinky -Srr [<package> ...]`

blinky will store its data according to the `XDG_BASE_DIR`-specification, specifically in the directories specified by the `XDG_CACHE_HOME` (build-files and built packages, `~/.cache/blinky` by default) and `XDG_DATA_HOME` (rewiew-results, `~/.local/share/blinky` by default) environment variables respectively.

## How to tweak

To enable tab completion in zsh, copy the
[`completion/_blinky`](completion/_blinky) file into a directory in your
`$FPATH` (or into a new directory that you add to the `$FPATH` before
`compinit` is called in your zsh startup).

Completion of package names requires querying AUR and thus has a high latency.
To avoid blocking the shell accidentally when completing `blinky -S <TAB>`
(which would result in a list of all AUR packages), a minimum of 4 characters
needs to be provided to trigger a query. This can be modified through `zstyle`:

```zsh
zstyle :completion:expand-word:complete:blinky:pkgcomp: numbers 4
```

This only applies to install operation. Locally installed packages get
completed for the `-Sr*` operations regardless of the number of provided
characters.
