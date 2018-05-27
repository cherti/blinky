# Blinky, testing branch

This is the testing branch of blinky. As long as there are no official releases, this is the testing base.


## How to use it

Just run blinky right out of the cloned directory; `python blinky.py --help` should give all relevant information you need.

In particular the currently available options are

  * package installation: `python blinky.py -S <package> [<package> ...]`
  * package search: `python blinky.py -Ss <package> [<package> ...]`
  * detailed package info: `python blinky.py -Si <package> [<package> ...]`
  * package updates: `python blinky.py -Syu`


## State

blinky is currently in the bug squashing phase before release. If you want to help testing it, this is very appreciated. Just clone this repository and checkout the testing-branch. Its readme includes all relevant information how to run blinky.

blinky is still rather ugly, but as the functionality is sufficiently stable by now, color and optics will be the next things to be done.

New features will be added as well, the author appreciates any requests of what might be a useful feature.


## Dependencies

All dependencies are present in the official ArchLinux package repositories, they are:

  * `python-requests`
  * `pyalpm`
