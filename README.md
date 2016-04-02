# README

## Introduction
Python script to save a local copy of all crates on [crates.io](https://crates.io/) and keep track of the upstream for [USTC mirrors](http://mirrors.ustc.edu.cn/).

This project is initially inspired by [@tennix](https://github.com/tennix)'s [crates-mirror](https://github.com/tennix/crates-mirror), and totally rewritten. You can find it on [pypi](https://pypi.python.org/pypi/cratesmirror).

## TODO
* [x] ~~download crates in a multi-threaded way if \<CratesDir> is empty~~
* [x] ~~packaging~~
* [x] ~~check database for missing crates~~

## Prerequisities
* Python >= 2.7.9
* at least 4G free disk space for hosting local crates

## Quick Start
```
# pip install cratesmirror
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
    // Download all crates only
    $ cratesmirror -d /var/lib/crates/crates.db -f /var/log/crates/debug.log

    // Find out missing crates and update the repository
    $ cratesmirror --checkdb -d /var/lib/crates/crates.db -f /var/log/crates/debug.log

    // Update repo and commit custom settings
    $ CRATES_DL='https://crates.mirrors.ustc.edu.cn/api/v1/crates' \
          cratesmirror -d /var/lib/crates/crates.db -f /var/log/crates/debug.log
```

## Note
* By default, the script will:
    * assume that registry index directory is located at `/srv/git/index`, and crates are saved at `/srv/www/crates`
    * save downloaded crate as `<CratesDir>/{name}/{name}-{version}.crate`
    * save the database file at `os.getcwd()/crates.db`
* If the environment variable `CRATES_DL` or `CRATES_API` is set, its value will be saved at `<RegistryDir>/config.json` and the changes will be committed automatically.
* After the first run, all you need to do is to run this script periodically using crontab-like tools or systemd.timers to sync with upstream.


## Proxy
You have to pass your proxy settings via ENV:
```
$ HTTP_PROXY="http://127.0.0.1:8080" HTTPS_PROXY="https://127.0.0.1:8081" \
      cratesmirror -i /srv/git/index -w /srv/www/crates -d /var/lib/crates/crates.db
```
