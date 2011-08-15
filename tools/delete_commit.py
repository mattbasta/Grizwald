import json
import sys
import urllib2

import couchdb


commit = sys.argv[1]

url = ('http://127.0.0.1:5984/grizwald/_design/tools/_view/commits?'
       'start_key=%%22%s%%22&end_key=%%22%s%%22' % (commit, commit))
id_doc = urllib2.urlopen(url).read()
ids = map(lambda r: r["value"], json.loads(id_doc)["rows"])

db = couchdb.Server()['grizwald']
for id in ids:
    print "Deleting %s" % id
    doc = db.get(id)
    db.delete(doc)

