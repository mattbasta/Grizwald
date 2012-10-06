
Deploying a job
===============

griz.py
-------

Place a file in the root of your project's repository called `griz.py`. This
file should accept a single command line argument. This argument is the path
of an individual file from the resource directory that was chosen during the
job submission process.

The standard output of the `griz.py` file is passed to the reducer.


The Reducer
-----------

The reducer is a URL referencing a python script that contains a function which
accepts two variables (strings from the standard outputs of `griz.py` or one
string and `None`). The function must be named `reduce()`.

The output of the reducer is expected to be a string. All input to the reducer
is stored in the form of a string.

- A variable named `current_job` is automatically declared in the global scope
  of the reducer. It contains the name of the current reduction job.

- A variable named `connection` is automatically declared in the global scope
  of the reducer. It contains a Redis connection which can be used by the
  reducer.

- If present, a function named `start()` (with no parameters) will be called
  when the job has been initialized.
