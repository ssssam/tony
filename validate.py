#!/usr/bin/python

import glob
import json

for morphology in glob.glob('*.morph'):
	f = open (morphology)
	try:
		json.load (f)
	except Exception:
		print "%s is bad" % morphology

