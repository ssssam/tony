
# Use JSON-GLib library instead of Python's Json module because representing
# the data using Python data structures causes the ordering to be mostly lost.
# JSON-GLib allows us to edit the data without reordering it.

from gi.repository import Json
import re
from tony_fedora import FedoraPackageDB, fedora_ignore_list
from tony_jhbuild import JhbuildModules

FILENAME = "gnome.morph"

JHBUILD_PATH = "/home/sam/gnome/src/jhbuild"

def __main__ ():
	chunk_dict = {}

	jhbuild = JhbuildModules (JHBUILD_PATH)

	# Load input stratum
	# - parser is a Json.Parser() for the file
	# - stratum_build_depends is a list of the chunks available in strata
	#   that are dependencies of the one that was specified.
	(parser, stratum_build_depends) = load_stratum (FILENAME)

	chunks = jhbuild.get_module_list('meta-gnome-core-shell')
	jhbuild_chunks = chunks.difference (stratum_build_depends)

	source_list = parser.get_root().get_object().get_member('sources')

	morph_chunks = set()
	for chunk_node in source_list.get_array().get_elements():
		chunk_object = chunk_node.get_object ()
		chunk_name = chunk_object.get_member('name').get_string()
		chunk_dict[chunk_name] = chunk_object

		morph_chunks.add (chunk_name)

		# Check dependencies match jhbuild
		jhbuild_build_depends = jhbuild.get_module_build_depends (chunk_name)
		jhbuild_build_depends = list (jhbuild_build_depends.difference (stratum_build_depends))
		jhbuild_build_depends.sort()

		new_build_depends = Json.Array()
		for bd in jhbuild_build_depends:
			new_build_depends.add_string_element (bd)

		chunk_object.set_array_member ('build-depends', new_build_depends)

	for new_chunk in jhbuild_chunks.difference(morph_chunks):
		chunk_object = Json.Object ()
		chunk_object.set_string_member ('name', new_chunk)

		repo = jhbuild.get_module_repo (new_chunk)
		if repo is not None:
			chunk_object.set_string_member ('repo', repo)
			chunk_object.set_string_member ('ref', 'master')

		jhbuild_build_depends = jhbuild.get_module_build_depends (new_chunk)
		jhbuild_build_depends = list (jhbuild_build_depends.difference (stratum_build_depends))
		jhbuild_build_depends.sort()

		new_build_depends = Json.Array()
		for bd in jhbuild_build_depends:
			new_build_depends.add_string_element (bd)

		chunk_object.set_array_member ('build-depends', new_build_depends)
		source_list.get_array().add_object_element (chunk_object)

	sort_sources (parser.get_root().get_object())

	write_json_postprocessed (FILENAME, parser.get_root())


def add_repo (source_node, repo_format):
	"""
	Add a "repo" key, using repo_format % chunk_name
	"""
	source_object = source_node.get_object ()
	source_name = source_object.get_member('name').get_string()

	if not source_object.has_member('repo'):
		source_object.set_string_member ('repo', repo_format % source_name)

		# Hack to fix the ordering ...

		if source_object.has_member('ref'):
			bd = source_object.get_member ('ref').copy ()
			source_object.remove_member ('ref')
			source_object.set_member ('ref', bd)

		if source_object.has_member('build-depends'):
			bd = source_object.get_member ('build-depends').copy ()
			source_object.remove_member ('build-depends')
			source_object.set_member ('build-depends', bd)


def add_build_depends_to_all (source_node, build_dep_name):
	"""
	Add a chunk to "build-depends" for each source in a stratum
	"""
	source_object = source_node.get_object ()

	if source_object.get_member('name').get_string() == build_dep_name:
		return

	# This is the method so the build-depends list remains sorted
	old_build_depends_node = source_object.get_member ("build-depends")
	new_build_depends = Json.Array()

	build_depends = []

	for bd in old_build_depends_node.get_array().get_elements():
		build_depends.append (bd.get_string())
	build_depends.append (build_dep_name)

	build_depends.sort()

	for bd in build_depends:
		new_build_depends.add_string_element (bd)

	source_object.set_array_member ('build-depends', new_build_depends)


def add_build_depends_from_fedora (chunk_dict, source_list):
	"""
	Work out "build-depends" from Fedora spec files
	"""
	fedora = FedoraPackageDB ('/home/sam/baserock/spec-cache', chunk_dict)

	for chunk_node in source_list.get_array().get_elements():
		chunk_object = chunk_node.get_object ()
		chunk_name = chunk_object.get_member('name').get_string()

		if chunk_name in fedora_ignore_list or chunk_name.startswith("xorg-proto-"):
			# These are all just xorg-x11-proto-devel in Fedora
			continue

		fedora_build_depends = fedora.get_build_depends (chunk_name)

		fedora_build_depends.sort()

		new_build_depends = Json.Array()
		for bd in fedora_build_depends:
			new_build_depends.add_string_element (bd)

		chunk_object.set_array_member ('build-depends', new_build_depends)


def sort_build_depends (chunk_object):
	old_build_depends_node = chunk_object.get_member ("build-depends")
	new_build_depends = Json.Array()

	build_depends = []

	for bd in old_build_depends_node.get_array().get_elements():
		build_depends.append (bd.get_string())

	build_depends.sort()

	for bd in build_depends:
		new_build_depends.add_string_element (bd)

	chunk_object.set_array_member ('build-depends', new_build_depends)

def sort_sources (stratum_object):
	source_list = stratum_object.get_member('sources')

	source_nodes = source_list.get_array().get_elements()

	source_dict = {}
	for node in source_nodes:
		name_node = node.get_object().get_member('name')
		source_dict[name_node.get_string()] = node
	sort_order = list(source_dict.keys())
	sort_order.sort(key=str.lower)

	sorted_nodes = []
	satisfied_list = []

	# Simple try-try-again algorithm to satisfy dependency ordering too
	while len (sort_order) > 0:
		postponed_list = []

		for source_name in sort_order:
			deps_satisfied = True

			source_node = source_dict[source_name]
			build_depends_node = source_node.get_object().get_member('build-depends')
			for d in build_depends_node.get_array().get_elements():
				if d.get_string() not in satisfied_list:
					deps_satisfied = False
					break

			if deps_satisfied:
				sorted_nodes.append (source_node)
				satisfied_list.append (source_name)
			else:
				postponed_list.append (source_name)

		sort_order = postponed_list

	new_source_list = Json.Array()
	for node in sorted_nodes:
		new_source_list.add_object_element (node.get_object())

	stratum_object.set_array_member ('sources', new_source_list)

def load_stratum (filename):
	"""
	Returns: tuplet of Json.Parser for current file, and set of chunks
	that are available in strata that this one depends on.
	"""
	parser = Json.Parser ()
	parser.load_from_file (filename)

	build_dep_chunk_set = set()
	build_dep_list = parser.get_root().get_object().get_member('build-depends')

	if build_dep_list is not None:
		for build_dep_node in build_dep_list.get_array().get_elements():
			# FIXME: use a more geological term for "the stratum below this one" :)
			child_file = build_dep_node.get_string () + ".morph"
			(child_parser, child_build_dep_set) = load_stratum (child_file)

			build_dep_chunk_set = set.union (build_dep_chunk_set, child_build_dep_set)

			child_source_list = child_parser.get_root().get_object().get_member('sources')

			for chunk_node in child_source_list.get_array().get_elements():
				chunk_object = chunk_node.get_object ()
				chunk_name = chunk_object.get_member('name').get_string()

				build_dep_chunk_set.add (chunk_name)

	return (parser, build_dep_chunk_set)

def write_json_postprocessed (filename, root_node):
	"""
	JSON-GLib's output is *almost* perfect ... but for some reason there's a
	space after dict keys and no way to turn it off. So we post-process its
	output before writing it to a file.
	"""

	generator = Json.Generator ()
	generator.set_indent (4)
	generator.set_pretty (True)

	generator.set_root (root_node)

	output = generator.to_data ()[0]

	# Remove space after object properties
	output = re.sub ('(\s+"[A-Za-z0-9-_]+") : ', '\\1: ', output)

	# Put empty arrays on single line
	output = re.sub (': \[\s+\]', ': []', output)

	f = open (filename, "w")
	f.write (output + "\n")
	f.close ()


__main__ ()

