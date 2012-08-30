#!/usr/bin/python

import glob
import json

errors = False

for morphology in glob.glob('*.morph'):
    f = open (morphology)
    try:
        data = json.load (f)
    except ValueError as e:
        print "Error in %s: %s" % (morphology, e)
        errors = True
        continue

    chunk_list = []

    if 'sources' not in data:
        # System, presumably
        continue

    for chunk in data['sources']:
        chunk_list.append (chunk['name'])

        for build_dep in chunk['build-depends']:
            if build_dep not in chunk_list:
                errors = True
                print "%s: unknown build-dep %s" % (chunk['name'], build_dep)

exit (errors)
