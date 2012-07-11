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
