#!/bin/bash

set -e

cd $(mktemp -d)

wget -O PKGBUILD https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=blinky

makepkg -sif
