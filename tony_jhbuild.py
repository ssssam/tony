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

					print name, module, default_repo, repo

					# Convert to morph format now, for whatever reason
					if repo == 'git.gnome.org':
						self.module_repos[name] = "gnome:%s" % module
					elif repo == 'freedesktop.org':
						self.module_repos[name] = "freedesktop:%s" % module
					else:
						if repo in repo_dict:
							self.module_repos[name] = repo_dict[repo] + module

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

	def get_module_list (self, metamodule):
		"""
		Get full set of modules required for one overall component
		"""
		def collect_deps (module_list):
			result = set(module_list)

			for module in module_list:
				if module not in self.module_deps:
					print "Unknown module: %s" % module
					continue

				result = result.union (collect_deps (self.module_deps[module]))
			return result

		return collect_deps (self.metamodule_deps[metamodule])

	def get_module_build_depends (self, module):
		return set(jhbuild_to_chunk(m) for m in self.module_deps[module])

	def get_module_repo (self, module):
		try:
			return self.module_repos [module]
		except KeyError as e:
			return None
