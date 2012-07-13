# Mungle info from jhbuild and fedora package database to attempt to get a
# full set of modules, gits, deps, build-deps etc for GNOME ...

# Currently must be run on a modern Fedora system as the local RPM database
# is used to check jhbuild package names before scraping the .spec file from
# fedora's git servers

import os
import re
import subprocess
import xml.dom.minidom


## System configuration!

JHBUILD_PATH = '/home/sam/gnome/src/jhbuild'

## Operation configuration!

jhbuild_inputs = [
	# apps & world - not needed for basic gnomeos
	# 'gnome-apps-3.6.modules',
	# 'gnome-world-3.6.modules'

	# core shell, fallback shell, core utilities and extras
	# also some core OS services (NetworkManager, gdm, dbus, etc)
	'gnome-suites-core-3.6.modules',
	'gnome-suites-core-deps-3.6.modules',

	# these are the stable deps we use tarball for, probably not required ...
	#'gnome-suites-core-deps-base-3.6.modules',
]

# jhbuild ID of packages we want to ignore
ignore_list = [
	# Already in baserock

	# Not yet!
	'WebKit',
	'seed',

	# Ignore bindings as long as possible
	'gtkmm',
	'java-gnome',
	'dbus-python',
	'pygobject',
]

jhbuild_inputs = [os.path.join (JHBUILD_PATH, 'modulesets', x) for x in jhbuild_inputs]

## Data!

class Chunk:
	def __init__ (self, id_jhbuild):
		self.id_jhbuild = id_jhbuild
		self.groups = []
		self.ignored = False
		self.dependencies_unresolved = []
		self.dependencies = []

	def dump (self):
		print self.id_jhbuild
		print
		print "Dependencies:"
		for f in self.dependencies:
			print "\t", f.id_jhbuild
		print "Groups:"
		print "\t", self.groups
		print

class ChunkSet:
	def __init__ (self):
		self.chunks = {}

	def add (self, id_jhbuild):
		global ignore_list

		if id_jhbuild in self.chunks:
			raise Exception ("Chunk '%s' already exists" % id_jhbuild)

		m = Chunk (id_jhbuild)
		self.chunks[id_jhbuild] = m

		if id_jhbuild in ignore_list:
			m.ignored = True

		return m

	def get (self, id_jhbuild = None):
		try:
			return self.chunks[id_jhbuild]
		except KeyError as e:
			return None


chunks = ChunkSet ()

metamodule_list = []

## Code!

def parse_jhbuild_moduleset (path):
	global chunks, metamodule_list

	dom = xml.dom.minidom.parse (path)

	base = dom.getElementsByTagName ("moduleset")[0]

	#for repo in base.getElementsByTagName ("repository"):
	#	print ("Repo")


	for element in base.getElementsByTagName ("autotools"):
		jhbuild_id = element.getAttribute("id")

		if jhbuild_id is None:
			print ("Warning: 'autotools' module without ID in '%s'" % path)
			continue

		chunk = chunks.add (jhbuild_id)

		dependencies = element.getElementsByTagName ("dependencies")

		if dependencies != []:
			for component in dependencies[0].getElementsByTagName ("dep"):
				dep_id = component.getAttribute ("package")
				chunk.dependencies_unresolved.append (dep_id)

	# Use the metamodules for grouping, this will help when definiting strata
	#
	for element in base.getElementsByTagName ("metamodule"):
		metamodule_list.append (element)


def resolve_dependencies ():
	"""
	Build an actual tree of deps
	"""

	global chunks

	for c in chunks.chunks.values():

		for dep_id in c.dependencies_unresolved:
			dep_chunk = chunks.get (id_jhbuild = dep_id)

			if dep_chunk is None:
				print ("Warning: Chunk %s has unresolved dependency %s" % (c.id_jhbuild, dep_id))
				continue

			c.dependencies.append (dep_chunk)
		c.dependencies_unresolved = None


def process_metamodules ():
	"""
	Deferred processing of metamodules, so dependencies can be resolved
	"""
	global metamodule_list
	for element in metamodule_list:
		group_name = element.getAttribute("id")

		if group_name is None:
			print ("Warning: 'metamodule' module without ID in '%s'" % path)
			continue

		dependencies = element.getElementsByTagName ("dependencies")[0]

		for component in dependencies.getElementsByTagName ("dep"):
			dep_id = component.getAttribute ("package")

			dep_chunk = chunks.get (id_jhbuild = dep_id)

			if dep_chunk is None:
				print ("Warning: unknown dep '%s' for metamodule '%s'" % (dep_id, group_name))
				continue

			dep_chunk.groups.append (group_name)



# Main !

for f in jhbuild_inputs:
	parse_jhbuild_moduleset (f)

resolve_dependencies ()
process_metamodules ()

#for c in chunks.chunks.values ():
#	c.dump ()
