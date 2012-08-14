## Import chunk information from jhbuild modulesets

import os
import xml.dom.minidom

jhbuild_inputs = [
	# apps & world - not needed for basic gnomeos
	'gnome-apps-3.6.modules',
	'gnome-world-3.6.modules',

	# core shell, fallback shell, core utilities and extras
	# also some core OS services (NetworkManager, gdm, dbus, etc)
	'gnome-suites-core-3.6.modules',
	'gnome-suites-core-deps-3.6.modules',

	# these are the stable deps we use tarball for, probably not required ...
	'gnome-suites-core-deps-base-3.6.modules',
]

jhbuild_ignore_list = set([
	# In foundation / Gtk+ under different names
	'expat',
	'gtk-doc',
	'gudev',

	# Keeps the dependencies down for now, we will probably need it later
	'gnome-control-center',

	# I'd like to keep a11y stuff in wherever possible, but this is big
	'mousetweaks',

	# Maybe a separate 'gnome-networking' stratum?
	# In practice we'd need to make some of these deps optional upstream
	#'glib-networking',
	'avahi',
	#'NetworkManager',
	#'network-manager-applet',
	'telepathy-mission-control',

	# Requires WebKit, which requires Gtk+-2, generally not want.
	# We need to configure evolution-data-server with --disable-goa.
	'gnome-online-accounts',

	# Nonsense
	'ConsoleKit',
	'gnome-packagekit',
	'gnome-screensaver',
	'PackageKit',
	# Also need to pass --disable-weather to evolution-data-server
	'libgweather',

	# Conditional dep of gnome-settings-daemon, not normal for embedded
	'libwacom',

	# Don't want
	'bluez'
])

def jhbuild_to_chunk (module):
	if module == 'gtk-doc':
		return 'gtk-doc-stub'
	return module

class JhbuildModules ():
	def __init__ (self, jhbuild_path):
		self.module_deps = {}
		self.module_repos = {}
		self.metamodule_deps = {}

		for f in jhbuild_inputs:
			self.parse_jhbuild_moduleset (os.path.join (jhbuild_path, 'modulesets', f))


	def parse_module_deps (self, node, path):
		name = node.getAttribute("id")

		if node.getAttribute("supports-parallel-builds") == "no":
			print "%s: no parallel builds" % name

		#autogen_args = node.getAttribute("autogen-sh") or node.getAttribute("autogenargs")
		#if autogen_args:
		#	print "%s: %s" % (name, autogen_args)

		dependencies_tag_list = node.getElementsByTagName ("dependencies")

		dependencies_list = set()
		if dependencies_tag_list != []:
			for component in dependencies_tag_list[0].getElementsByTagName ("dep"):
				dep_name = component.getAttribute ("package")
				dependencies_list.add (dep_name)

		return (name, dependencies_list)


	def parse_jhbuild_moduleset (self, path):
		dom = xml.dom.minidom.parse (path)

		base = dom.getElementsByTagName ("moduleset")[0]

		default_repo = None
		repo_dict = {}
		for repo in base.getElementsByTagName ("repository"):
			if repo.getAttribute("type") != "git":
				continue

			name = repo.getAttribute("name")
			href = repo.getAttribute("href")
			repo_dict[name] = href

			if repo.getAttribute("default") == "yes":
				default_repo = name

		for module_list in [base.getElementsByTagName ("autotools"),
		                    base.getElementsByTagName ("tarball"),
		                    base.getElementsByTagName ("cmake")]:
			for element in module_list:
				(name, deps) = self.parse_module_deps (element, path)

				if name in self.module_deps:
					print ("Warning: duplicate module '%s' in %s" % (name, path))
					continue

				self.module_deps[name] = deps

				branch = element.getElementsByTagName ("branch")
				if len(branch) > 0:
					branch = branch[0]
					for p in branch.getElementsByTagName ("patch"):
						print "%s: patch: %s" % (name, p.getAttribute("file"))
					repo = branch.getAttribute("repo") or default_repo
					module = branch.getAttribute("module") or name

					# Convert to morph format now, for whatever reason
					if repo == 'git.gnome.org':
						self.module_repos[name] = "gnome:%s" % module
					elif repo in repo_dict:
						repo_href = repo_dict[repo]
						if repo_href.startswith ('git://anongit.freedesktop.org/'):
							self.module_repos[name] = "freedesktop:%s" % (repo_href[30:] + module)
						else:
							self.module_repos[name] = repo_dict[repo] + '/' + module
					else:
						print "%s: Unknown repo: %s" % (name, repo)

		for element in base.getElementsByTagName ("metamodule"):
			(name, deps) = self.parse_module_deps (element, path)

			if name in self.metamodule_deps:
				print ("Warning: duplicate metamodule '%s' in %s" % (name, path))
				continue
			self.metamodule_deps[name] = deps


	def dump (self):
		print "Modules:"
		for m in self.module_deps.keys():
			print m

		print "\nMetamodules:"
		for m in self.metamodule_deps.keys():
			print m
			for d in self.metamodule_deps[m]:
				print "\t%s" % d

	def chunk_is_module (self, chunk):
		"""
		True if Baserock chunk name exists as a jhbuild module as well
		"""
		return chunk in self.module_deps.keys()

	def get_module_list (self, metamodule):
		"""
		Get full set of modules required for one overall component
		"""
		def collect_deps (module_list):
			result = set(module_list)
			result = result.difference (jhbuild_ignore_list)

			for module in result:
				if module not in self.module_deps:
					print "Unknown module: %s" % module
					continue

				result = result.union (collect_deps (self.module_deps[module]))
			return result

		return collect_deps (self.metamodule_deps[metamodule])

	def get_module_build_depends (self, module):
		build_depends = set(jhbuild_to_chunk(m) for m in self.module_deps[module])
		build_depends = build_depends.difference (jhbuild_ignore_list)
		return build_depends

	def get_module_repo (self, module):
		try:
			return self.module_repos [module]
		except KeyError as e:
			return None
