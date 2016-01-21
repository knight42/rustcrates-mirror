# README

## Introduction
Python script to save a local copy of all crates on [crates.io](https://crates.io/) and keep track of the upstream for [USTC mirrors](http://mirrors.ustc.edu.cn/).

This project is initially inspired by [@tennix](https://github.com/tennix)'s [crates-mirror](https://github.com/tennix/crates-mirror), and totally rewritten.

## TODO
* [ ] download crates in a multi-threaded way if \<CratesDir> is empty

## Prerequisities
* Python >= 2.7.9
* at least 4G free disk space for hosting local crates

## Note
* The first run may be rather slow, because the script always downloads crates synchronously at present. 
* By default, the script will:
    * assume that registry index directory is located at `/srv/git/index`, and crates are saved at `/srv/www/crates`
    * save downloaded crate as \<CratesDir>/{name}/{name}-{version}.crate
    * save the database file at `os.getcwd()/crates.db`

## Quick Start
```
pip install -r requirements.txt
python mirror.py
```
Note that the first run of this script can take hours, you have to be patient.

After that, all you need to do is to run this script periodically using crontab-like tools or systemd.timers etc. to keep sync with upstream.

## Configuration
Since the script is well-documented IMO :), you can easily modify the script to meet your needs.
