#!/usr/bin/python -O
# -*- coding: utf-8 -*-

import os
import argparse
from ._mirror import CratesMirror

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='crates-mirror',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     epilog='''Available environment variables: HTTP_PROXY, HTTPS_PROXY, CRATES_DL, CRATES_API''')
    parser.add_argument('-i', '--index', help='registry index directory', default='/srv/git/index')
    parser.add_argument('-w', '--crates', help='crates directory', default='/srv/www/crates')
    parser.add_argument('-d', '--dbpath', help='database file path', default=None)
    parser.add_argument('-f', '--logfile', help='log file path', default=None)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)

    custom_config = {'api': 'https://crates.io', 'dl': 'https://crates.io/api/v1/crates'}
    if os.getenv('CRATES_DL'):
        custom_config['dl'] = os.getenv('CRATES_DL')
    if os.getenv('CRATES_API'):
        custom_config['api'] = os.getenv('CRATES_API')

    args = parser.parse_args()

    with CratesMirror(args.index, args.crates, config=custom_config,
                      dbpath=args.dbpath, logfile=args.logfile,
                      debug=args.verbose) as mirror:
        mirror.update_repo()

