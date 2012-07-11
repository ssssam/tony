
# Use JSON-GLib library instead of Python's Json module because representing
# the data using Python data structures causes the ordering to be mostly lost.
# JSON-GLib allows us to edit the data without reordering it.

from gi.repository import Json
import re
from tony_fedora import FedoraPackageDB, fedora_ignore_list

FILENAME = "x.morph"

def __main__ ():
	chunk_dict = {}

	# Load all input strata
	parser = Json.Parser ()
	parser.load_from_file (FILENAME)

	source_list = parser.get_root().get_object().get_member('sources')

	for chunk_node in source_list.get_array().get_elements():
		# Do something here for each chunk
		chunk_object = chunk_node.get_object ()
		chunk_name = chunk_object.get_member('name').get_string()

		chunk_dict[chunk_name] = chunk_object

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

	write_json_postprocessed (FILENAME, parser.get_root ())


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

def add_build_depends (source_node):
	"""
	Add empty "build-depends", which is now mandatory
	"""
	source_object = source_node.get_object ()

	if not source_object.has_member('build-depends'):
		empty_array = Json.Array ()
		empty_array_node = source_node.get_parent().copy ()
		empty_array_node.set_array (empty_array)
		source_object.set_member ('build-depends', empty_array_node)


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

