## Process Fedora spec files to get a set of build-depends.
##
## Currently uses Yum to test validity and whatprovides, so needs to be run on
## a Fedora system although the packages do not actually need to be installed.

import os
import re
import subprocess

## Chunks that don't map sensibly onto Fedora packages and will have to be
## dealt with by hand.
##
fedora_ignore_list = [
	# In xorg-x11-apps
	'xorg-app-xinit',
	'xorg-app-xkbcomp',
	# In xorg-x11-utils
	'xorg-util-makedepend',
	# In xorg-x11-xtrans-devel ?
	'xorg-lib-libxtrans',
	# In xcb-util ?
	'xcb-pthread-stubs',
	# Doing their own thing
	'mesa', 'drm'
]

## Fedora packages that we can ignore when listed as BuildRequires: !
##
## Ideally this tool would load all of the morphs and handle build-depends that
## are valid but exist in a different stratum. However ... time :(
##
build_dep_ignore_list = [
	'autoconf',
	'automake',
	'doxygen',
	'ed',
	'gettext',
	'graphviz',
	'intltool',
	'libgcrypt',
	'libtool',
	'libuuid',
	'libxml2-python',
	'lynx',
	'perl(XML::Parser)',
	'pkgconfig',
	'python',
	'python2',
	'xmlto',
	'xz',
	'zlib'
]

def check_package_exists (name):
	output = subprocess.check_output ('repoquery -C %s' % name, shell = True)

	if len(output) > 0:
		return True
	return False

def get_fedora_package_for_build_requires (owner, fedora_build_requires):
	yum_query = 'repoquery -C --whatprovides "%s" --qf "%%{NAME}\\n"'

	try:
		output = subprocess.check_output (yum_query % fedora_build_requires, shell = True)
	except subprocess.CalledProcessError as e:
		print "Warning: %s: Yum output: %s" % (owner, e.output);
		return None

	candidate_list = output.split()
	if candidate_list is None:
		print "Warning: %s: nothing provides %s" % (owner, fedora_build_requires)
		return None

	return candidate_list[0]


class FedoraPackageDB ():
	# We need to map both ways, from Baserock chunk <--> Fedora package.
	# On __init__() we look up package names for each chunk, and store them in
	# a hash, with the net result that literal mappings only need to be written
	# one way.
	def chunk_to_fedora_package (self, chunk_name):
		mapping = {
			'fontutils': 'xorg-x11-font-utils',
			'xcb-libxcb': 'libxcb',
			'xorg-lib-libXRes': 'libXres',
			'xorg-util-macros': 'xorg-x11-util-macros',
			'xserver': 'xorg-x11-server-Xorg'
		}

		if chunk_name in mapping:
			return mapping[chunk_name]

		parts = chunk_name.split ('-')

		if len (parts) == 3:
			if parts[0] == 'xorg' and parts[1] == 'lib':
				return parts[2]

		if len (parts) == 5:
			if parts[0] == 'xorg' and parts[1] == 'driver' and parts[2] == 'xf86':
				return 'xorg-x11-drv-' + parts[4]

		return chunk_name

	# A BuildRequires: can be more complex, but thanks to rpm -q --whatprovides
	# our life isn't too difficult.
	def fedora_build_dependency_to_chunk (self, owner, fedora_build_dep):
		# Known exceptions
		if fedora_build_dep == 'pkgconfig(xproto)':
			return 'xorg-proto-x11proto'

		if fedora_build_dep == 'xorg-x11-xtrans-devel':
			return 'xorg-lib-libxtrans'

		if fedora_build_dep.startswith('pkgconfig(') and fedora_build_dep.endswith('proto)'):
			return 'xorg-proto-' + fedora_build_dep[10:-1]

		if fedora_build_dep == 'xorg-x11-proto-devel':
			# ARRGH, but we can't know which one
			print "Unhandled: %s depends on SOME protocol headers" % owner
			return None

		# Try ignore list now to avoid RPM errors
		if fedora_build_dep in build_dep_ignore_list:
			return None

		package_name = get_fedora_package_for_build_requires (owner, fedora_build_dep)

		if package_name is None:
			return None

		if package_name.endswith ('-devel'):
			package_name = package_name[:-6]

		# Try ignore list again
		if fedora_build_dep in build_dep_ignore_list:
			return None

		if package_name in self.fedora_package_to_chunk:
			return self.fedora_package_to_chunk[package_name]

	def get_srcpackage_name (self, package_name):
		# We need a couple of special-cases here, because the source package
		# doesn't *have* to correspond to its output packages at all

		if package_name == 'xorg-x11-server-Xorg':
			return 'xorg-x11-server'
		return package_name


	# However, Fedora can throw a lot more at us in BuildRequires: so this
	# function is not simple either.

	def __init__ (self, cache_path, chunk_dict):
		self.cache_path = cache_path
		self.chunk_list = chunk_dict.keys()
		self.fedora_package_to_chunk = {}

		if not os.path.exists (self.cache_path):
			os.makedirs (self.cache_path)

		for chunk_name in self.chunk_list:
			if chunk_name in fedora_ignore_list or chunk_name.startswith("xorg-proto-"):
				# These are all just xorg-x11-proto-devel in Fedora
				continue

			fedora_package_name = self.chunk_to_fedora_package (chunk_name)

			if check_package_exists (fedora_package_name) == False:
				print ('No Fedora package for chunk %s (tried %s)' % (chunk_name, fedora_package_name))
				continue

			self.fedora_package_to_chunk[fedora_package_name] = chunk_name

			self.check_and_download_spec_file (self.get_srcpackage_name (fedora_package_name))

	def check_and_download_spec_file (self, srcpackage_name):
		spec_file_name = os.path.join (self.cache_path, srcpackage_name + '.spec')

		if os.path.exists(spec_file_name) and os.stat(spec_file_name).st_size > 0:
			return

		# Scrape from Fedora's gitweb
		FEDORA_SPEC_FILE_URL = "http://pkgs.fedoraproject.org/gitweb/?p=%s.git;a=blob_plain;f=%s.spec"
		spec_url = FEDORA_SPEC_FILE_URL % (srcpackage_name, srcpackage_name)
		subprocess.call ('wget -c "%s" --output-document=%s' % (spec_url, spec_file_name), shell = True)


	def get_build_depends (self, chunk_name):
		chunk_fedora_package_name = self.chunk_to_fedora_package (chunk_name)

		spec_file = os.path.join (self.cache_path, self.get_srcpackage_name (chunk_fedora_package_name) + '.spec')

		chunk_build_depends_list = []

		f = open (spec_file, "r")
		for line in f:
			if not line.startswith('BuildRequires:'):
				continue

			components = line.split()[1:]

			while len (components) > 0:
				dep = components.pop(0)
				if len (components) >= 2 and components[0] == '>=':
					del components [0:2]

				dep_chunk_name = self.fedora_build_dependency_to_chunk (chunk_name, dep)

				if dep_chunk_name is None:
					# Ignored, should have given an error already
					pass
				elif dep_chunk_name not in self.chunk_list:
					print "Warning: %s has unknown dep: '%s'" % (chunk_name, dep_chunk_name)
				else:
					chunk_build_depends_list.append (dep_chunk_name)

		return chunk_build_depends_list
