CratesMirror
============

.. image:: https://img.shields.io/pypi/v/cratesmirror.svg
    :target: https://pypi.python.org/pypi/cratesmirror

About
=====

Download all crates on `crates.io <https://crates.io>`__

Requirement
============

- Python >= 2.7.9
-  `requests <https://pypi.python.org/pypi/requests/>`__
-  `GitPython <https://pypi.python.org/pypi/GitPython/>`__
- At least 4G free disk space for hosting local crates

Installation
============

::

    # pip install cratesmirror

Usage
======

.. code-block:: bash

    $ cratesmirror -h

    usage: cratesmirror [-h] [-i INDEX] [-w CRATES] [-d DBPATH] [-f LOGFILE]
                        [-c CHECKDB] [-v]

    optional arguments:
      -h, --help            show this help message and exit
      -i, --index INDEX     registry index directory (default: /srv/git/index)
      -w, --crates CRATES   crates directory (default: /srv/www/crates)
      -d, --dbpath DBPATH   database file path (default: None)
      -f, --logfile LOGFILE
                            log file path (default: None)
      -c, --checkdb CHECKDB
                            check database for missing crates (default: False)
      -v, --verbose

    Available environment variables: HTTP_PROXY, HTTPS_PROXY, CRATES_DL, CRATES_API


    Examples:
    # Download all crates only
    $ cratesmirror -d /var/lib/crates/crates.db -f /var/log/crates/debug.log

    # Find out missing crates, then update the repository
    $ cratesmirror --checkdb -d /var/lib/crates/crates.db -f /var/log/crates/debug.log

    # Update repo and commit custom settings
    $ CRATES_DL='https://crates.mirrors.ustc.edu.cn/api/v1/crates' \
          cratesmirror -d /var/lib/crates/crates.db -f /var/log/crates/debug.log

    # Using proxy
    $ HTTPS_PROXY='https://127.0.0.1:8081' \
          cratesmirror -d /var/lib/crates/crates.db -f /var/log/crates/debug.log


Or use it in script

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

Note
======

- By default, the script will:
    - assume that registry index directory is located at :code:`/srv/git/index`, and crates are saved at :code:`/srv/www/crates`
    - save downloaded crate as :code:`<CratesDir>/{name}/{name}-{version}.crate`
    - save the database file at :code:`os.getcwd()/crates.db`
- If the environment variable :code:`CRATES_DL` or :code:`CRATES_API` is set, its value will be saved at :code:`<IndexDir>/config.json` and the changes will be committed automatically.
- After the first run, all you need to do is to run this script periodically using crontab-like tools or systemd.timers to sync with upstream.


.. :changelog:

ChangeLog
---------------

1.1.1
+++++++++++

**Miscellaneous**

- Add changelog

1.1.0
++++++++++++++++++

**Improvement**

- Always download crates using multithreading

1.0.4
++++++++++++++++++

**Feature**

- Add -c/--checkdb option, enable users to check database for missing crates

1.0.3
++++++++++++++++++

**Improvement**

- When <CratesDir> is empty, download all crates in a multithreaded way

1.0.2
++++++++++++++++++

- Naive crawler
