CratesMirror
============

About
=====

Download all crates on `crates.io <https://crates.io>`__

Dependencies
============

Python >= 2.7.9

-  `requests <https://pypi.python.org/pypi/requests/>`__
-  `GitPython <https://pypi.python.org/pypi/GitPython/>`__

Installation
============

::

    $ pip install cratesmirror


Usage
======

.. code-block:: python
    
    from cratesmirror import CratesMirror

    indexdir = '/srv/git/index'
    cratesdir = '/srv/www/crates'
    config = {'dl': 'https://crates.mirrors.ustc.edu.cn/api/v1/crates',
              'api': 'https://crates.io'}
    # By default, it will be saved at os.getcwd()/crates.db
    dbpath = '/var/lib/cratesmirror/crates.db'

    with CratesMirror(indexdir, cratesdir, config=config, dbpath=dbpath) as mirror:
        mirror.update_repo()

    # with proxy
    proxies = {
      "http": "http://10.10.1.10:3128",
      "https": "http://10.10.1.10:1080",
    }
    with CratesMirror(indexdir, cratesdir, config=config, proxy=proxies, dbpath=dbpath) as mirror:
        mirror.update_repo()


Or use it in CLI

::

    $ python -m cratesmirror -h


