#!/usr/bin/python

from xdg import BaseDirectory
import os, shutil

data  = BaseDirectory.save_data_path('blinky')
cache = BaseDirectory.save_cache_path('blinky')
blinkydir = os.path.abspath(os.path.expanduser('~/.blinky'))

if not os.path.isdir(blinkydir):  # backward compatibility
	print("No ~/.blinky found, nothing to migrate")
	exit()

def migrate(src, target, execute=False):
	if not execute:
		print("Moving ~/blinky/{} to {}".format(src, target))
	else:
		src = os.path.join(blinkydir, src)
		shutil.move(src, target)

print("Gonna start migrating ~/.blinky:")
migrate("build", cache)
migrate("logs", cache)
migrate("cache", os.path.join(cache, 'pkg'))

input("Proceed? (Ctrl+C if not)")

migrate("build", cache, execute=True)
migrate("logs", cache, execute=True)
migrate("cache", os.path.join(cache, 'pkg'), execute=True)

shutil.rmtree(blinkydir)
