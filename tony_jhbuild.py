## Import chunk information from jhbuild modulesets

import os
import xml.dom.minidom

def jhbuild_to_chunk_name(module):
    if module == 'gtk-doc':
        return 'gtk-doc-stub'
    return module

def jhbuild_to_morph_repo(repo_dict, repo, module):
    if repo == 'git.gnome.org':
        return "gnome:%s" % module

    if repo in repo_dict:
        repo_href = repo_dict[repo]
        if repo_href.startswith ('git://anongit.freedesktop.org/'):
            return "freedesktop:%s" % (repo_href[30:] + module)
        else:
            return repo_dict[repo] + '/' + module

    print "%s: Unknown repo: %s" % (module, repo)
    return None


class JhbuildModules():
    def __init__(self, jhbuild_path, jhbuild_inputs, ignore_list):
        self.module_deps = {}
        self.module_repos = {}
        self.metamodule_deps = {}
        self.ignore_list = ignore_list

        for m in jhbuild_inputs:
            f = os.path.join(jhbuild_path, 'modulesets', m)
            self._parse_jhbuild_moduleset(f)


    def _parse_module_deps(self, node, path):
        name = node.getAttribute("id")

        if node.getAttribute("supports-parallel-builds") == "no":
            print "%s: no parallel builds" % name

        #autogen_args = node.getAttribute("autogen-sh") or node.getAttribute("autogenargs")
        #if autogen_args:
        #    print "%s: %s" % (name, autogen_args)

        dependencies_tag_list = node.getElementsByTagName("dependencies")

        dependencies_list = set()
        if dependencies_tag_list != []:
            for component in dependencies_tag_list[0].getElementsByTagName("dep"):
                dep_name = component.getAttribute ("package")
                dependencies_list.add (dep_name)

        return (name, dependencies_list)


    def _parse_jhbuild_moduleset(self, path):
        dom = xml.dom.minidom.parse(path)

        base = dom.getElementsByTagName("moduleset")[0]

        default_repo = None
        repo_dict = {}
        for repo in base.getElementsByTagName("repository"):
            if repo.getAttribute("type") != "git":
                continue

            name = repo.getAttribute("name")
            href = repo.getAttribute("href")
            repo_dict[name] = href

            if repo.getAttribute("default") == "yes":
                default_repo = name

        for module_list in [base.getElementsByTagName("autotools"),
                            base.getElementsByTagName("tarball"),
                            base.getElementsByTagName("cmake")]:
            for element in module_list:
                (name, deps) = self._parse_module_deps(element, path)

                if name in self.module_deps:
                    print ("Warning: duplicate module '%s' in %s" % (name, path))
                    continue

                self.module_deps[name] = deps

                branch = element.getElementsByTagName("branch")
                if len(branch) > 0:
                    branch = branch[0]
                    for p in branch.getElementsByTagName("patch"):
                        print "%s: patch: %s" % (name, p.getAttribute("file"))
                    repo = branch.getAttribute("repo") or default_repo
                    module = branch.getAttribute("module") or name

                    self.module_repos[name] = jhbuild_to_morph_repo(repo_dict,
                                                                    repo,
                                                                    module)

        for element in base.getElementsByTagName("metamodule"):
            (name, deps) = self._parse_module_deps(element, path)

            if name in self.metamodule_deps:
                print ("Warning: duplicate metamodule '%s' in %s" % (name, path))
                continue
            self.metamodule_deps[name] = deps


    def dump(self):
        print "Modules:"
        for m in self.module_deps.keys():
            print m

        print "\nMetamodules:"
        for m in self.metamodule_deps.keys():
            print m
            for d in self.metamodule_deps[m]:
                print "\t%s" % d

    def chunk_is_module (self, chunk):
        '''True if Baserock chunk name exists as a jhbuild module as well'''
        return chunk in self.module_deps.keys()

    def get_module_list(self, metamodule):
        '''Get full set of modules required for one overall component'''
        def collect_deps(module_list):
            result = set(module_list)
            result = result.difference(self.ignore_list)

            for module in result:
                if module not in self.module_deps:
                    print "Unknown module: %s" % module
                    continue

                result = result.union(collect_deps(self.module_deps[module]))
            return result

        return collect_deps(self.metamodule_deps[metamodule])

    def get_module_build_depends(self, module):
        build_depends = set(jhbuild_to_chunk_name(m) \
                            for m in self.module_deps[module])
        build_depends = build_depends.difference(self.ignore_list)
        return build_depends

    def get_module_repo(self, module):
        try:
            return self.module_repos[module]
        except KeyError as e:
            return None
