# README

## Introduction
Python script to save a local copy of all crates on [crates.io](https://crates.io/) and keep track of the upstream for [USTC mirrors](http://mirrors.ustc.edu.cn/).

This project is initially inspired by [@tennix](https://github.com/tennix)'s [crates-mirror](https://github.com/tennix/crates-mirror), and totally rewritten. You can find it on [pypi](https://pypi.python.org/pypi/cratesmirror/1.0.3).

## TODO
* [x] ~~download crates in a multi-threaded way if \<CratesDir> is empty~~
* [x] ~~packaging~~

## Prerequisities
* Python >= 2.7.9
* at least 4G free disk space for hosting local crates

## Note
* ~~The first run may be rather slow, because the script always downloads crates synchronously at present.~~ 
* By default, the script will:
    * assume that registry index directory is located at `/srv/git/index`, and crates are saved at `/srv/www/crates`
    * save downloaded crate as \<CratesDir>/{name}/{name}-{version}.crate
    * save the database file at `os.getcwd()/crates.db`

## Quick Start
```
$ pip install cratesmirror
$ python -m cratesmirror -h

    usage: crates-mirror [-h] [-i INDEX] [-w CRATES] [-d DBPATH] [-f LOGFILE] [-v]

    optional arguments:
      -h, --help            show this help message and exit
      -i, --index INDEX
                            registry index directory (default: /srv/git/index)
      -w, --crates CRATES
                            crates directory (default: /srv/www/crates)
      -d, --dbpath DBPATH
                            database file path (default: None)
      -f, --logfile LOGFILE
                            log file path (default: None)
      -v, --verbose

    Available environment variables: HTTP_PROXY, HTTPS_PROXY, CRATES_DL, CRATES_API


$ CRATES_DL='https://crates.mirrors.ustc.edu.cn/api/v1/crates' \
          python -m cratesmirror -d /var/lib/crates/crates.db -f /var/log/crates/debug.log
```
Note that the first run of this script may take a while, you have to be patient.

After that, all you need to do is to run this script periodically using crontab-like tools or systemd.timers etc. to keep sync with upstream.


## Proxy
You have to pass the proxy setting via ENV:
```
$ HTTP_PROXY="http://127.0.0.1:8080" HTTPS_PROXY="https://127.0.0.1:8081" \
          python -m cratesmirror -i /srv/git/index -w /srv/www/crates -d /var/lib/crates/crates.db
```
