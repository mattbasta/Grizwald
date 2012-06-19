====================
 Professor Grizwald
====================

There are two parts to Grizwald. The first is the indexer, which collects the
information from the validator. The second part is the server, which performs
analysis on the information collected using a combination of Python code and
CouchDB map/reduce procedures to chew through the data.


---------
 Indexer
---------

The indexer can be found, along with a plethora of documentation, in the
``/indexer`` subdirectory.

--------
 Server
--------

The server is a simple Tornado server that draws on CouchDB. It creates
interesting graphs and charts that help to visualize how the output of the
validator has changed over time.


Setup
=====

The setup process is relatively straight-forward:

#. Install the dependencies using ``pip install -r requirements.txt``
#. Start the server: ``cd server && ./main.py``

That's it! By default, the server should start on port 8080, meaning it will
be accessible from http://localhost:8080/.


--------------------
 Setting Up CouchDB
--------------------

First, install CouchDB using the method most appropriate for your platform.

Next, create the databases ``grizwald`` and ``grizwald_js`` using Futon.

Last, create a design document in ``grizwald`` with the ID
``_design/performance``. The properties of the document can be found in
``/setup/performance.json``.

