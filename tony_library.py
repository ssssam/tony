### Historical examples
###

def parse_freedesktop_git_repos ():
	"""
	Parse 'cgit' page listing full path of available XOrg repositories
	"""

	import BeautifulSoup

	HTML_DOC = "../xorg-repos-cgit.html"

	html = open (HTML_DOC)
	soup = BeautifulSoup.BeautifulSoup (html)

	repo_links = soup.findAll ('td', { 'class': 'sublevel-repo' })

	chunk_to_xorg_repo = {}

	parse = re.compile ('xorg/([a-zA-Z0-9-]+)/([a-zA-Z0-9-]+)')
	for l in repo_links:
		repo_name = l.a.contents[0]
		components = parse.match (repo_name)
		if components is not None and components.lastindex == 2:
			chunk_to_xorg_repo[components.group(2)] = repo_name
		else:
			print "Note: ignored ", repo_name

	return chunk_to_xorg_repo


def fix_xorg_chunk_repo (source_node, chunk_to_xorg_repo):
	source_object = source_node.get_object ()
	source_name = source_object.get_member('name').get_string()

	if source_name not in chunk_to_xorg_repo:
		print "Warning: no Xorg repo detected for chunk %s" % source_name
		return

	if not source_object.has_member('repo'):
		repo_name = chunk_to_xorg_repo [source_name]

		source_object.set_string_member ('repo', "freedesktop:%s" % repo_name)

		# Hack to fix the ordering ...

		if source_object.has_member('ref'):
			bd = source_object.get_member ('ref').copy ()
			source_object.remove_member ('ref')
			source_object.set_member ('ref', bd)

		if source_object.has_member('build-depends'):
			bd = source_object.get_member ('build-depends').copy ()
			source_object.remove_member ('build-depends')
			source_object.set_member ('build-depends', bd)

def fix_xorg_chunk_name (source_node, chunk_to_xorg_repo):
	source_object = source_node.get_object ()

	source_name = source_object.get_member('name').get_string()

	if source_name not in chunk_to_xorg_repo:
		print "Warning: no Xorg repo detected for chunk %s" % source_name
	else:
		repo_name = chunk_to_xorg_repo[source_name]
		new_source_name = repo_name.replace('/','-')
		source_object.set_string_member ('name', new_source_name)

	if source_object.has_member('build-depends'):
		build_depends = source_object.get_member('build-depends').get_array()

		for build_dep_node in build_depends.get_elements():
			build_dep_name = build_dep_node.get_string()
			if build_dep_name in chunk_to_xorg_repo:
				build_dep_node.set_string (chunk_to_xorg_repo[build_dep_name].replace('/','-'))


def find_unneeded_chunks ():
	'''Detect chunks that were branched just to set configure arguments'''

	unneeded_chunks = {}
	for chunk_morph in glob.glob ('/home/sam/baserock/delta/*/*.morph'):
		data = json.load(open(chunk_morph))
		if data['build-system'] == 'autotools' and \
		   'configure-commands' in data and \
		   'build-commands' not in data and \
		   'install-commands' not in data:
			cmds = data['configure-commands']

			if len (cmds) == 2 and \
			   (cmds[0] == 'NOCONFIGURE=1 ./autogen.sh' or \
			    cmds[0] == './autogen.sh'):
				configure_cmd = cmds[1]
			elif len (cmds) == 1 and cmds[0].startswith('./autogen.sh'):
				configure_cmd = cmds[0]
			else:
				print "Ignore: ", chunk_morph
				continue

			if configure_cmd.startswith ('./configure --prefix="$PREFIX" '):
				configure_cmd = configure_cmd[len('./configure --prefix="$PREFIX" '):]
			elif configure_cmd.startswith ('./autogen.sh --prefix="$PREFIX" '):
				configure_cmd = configure_cmd[len('./autogen.sh --prefix="$PREFIX" '):]
			else:
				print "Ignore: ", chunk_morph
				continue

			unneeded_chunks[data['name']] = configure_cmd


def stratum_process():
	for stratum_morph in ['gnome.morph', 'x.morph', 'gtk+.morph', 'gnome-legacy.morph']:
		parser = Json.Parser ()
		parser.load_from_file (stratum_morph)

		source_list = parser.get_root().get_object().get_member('sources')
		for source in source_list.get_array().get_elements():
			environment = source.get_object().get_member('environment')
			if environment:
				args_string = environment.get_object().get_member('BR_CONFIGURE_FLAGS')
				args_array = Json.Array()
				for arg in args_string.get_string().split():
					args_array.add_string_element(arg)
				source.get_object().set_array_member('args', args_array)
				source.get_object().remove_member('environment')

		fix_stratum_sorting (parser.get_root().get_object())

		write_json_postprocessed (stratum_morph, parser.get_root())

