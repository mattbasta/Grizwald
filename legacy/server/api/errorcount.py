import json

from tornado.httpclient import AsyncHTTPClient
from tornado.web import RequestHandler, asynchronous

import constants


class ErrorCountHandler(RequestHandler):

    @asynchronous
    def get(self):
        client = AsyncHTTPClient()
        callback_name = self.get_argument("callback")
        if not all(a.isalnum() or a == "_" for a in callback_name):
            return

        def callback(response):
            if not response.error:
                r = json.loads(response.body)
                error_types = set()
                data = {}
                output_data = {}
                self.set_header("Content-type", "text/javascript")
                self.write("%s(" % callback_name)
                for row in r["rows"]:
                    commit = tuple(row["key"][:2])
                    if commit not in data:
                        data[commit] = {}
                        output_data[commit] = []
                    error_type = tuple(row["key"][2:])
                    if error_type[0] == "zzzzz":
                        continue
                    data[commit][error_type] = row["value"]
                    output_data[commit].append((error_type, row["value"]))
                    error_types.add(error_type)

                for row in data:
                    for et in error_types:
                        if et not in data[row]:
                            output_data[row].append((et, 0))

                def break_out_totals(d):
                    return zip(data.keys(), data.values())

                data = {"rows": zip(output_data.keys(), output_data.values())}
                self.write(json.dumps(data))
                self.write(");")
            self.finish()

        with open("/opt/error_counts.json") as f:

            class MockErrors(object):
                def __init__(self, data):
                    self.error = None
                    self.body = data

            callback(MockErrors(f.read()))

        return

        client.fetch("%s/grizwald/_design/performance/_view/error_counts?"
                     "group=true" % constants.COUCH_URL, callback,
                     connect_timeout=60*5, request_timeout=60*5)

