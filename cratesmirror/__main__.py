#!/usr/bin/python -O
# -*- coding: utf-8 -*-

import os
import argparse
from ._mirror import CratesMirror

# Inspired by http://stackoverflow.com/a/25334100/4725840
class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings:
            metavar, = self._metavar_formatter(action, action.dest)(1)
            return metavar
        else:
            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                return ', '.join(action.option_strings)
            # if the Optional takes a value, format is:
            #    -s, --long ARGS
            else:
                default = action.dest.upper()
                args_string = self._format_args(action, default)
                option_string = ', '.join(action.option_strings)
            return '{} {}'.format(option_string, args_string)

def main():
    parser = argparse.ArgumentParser(prog='cratesmirror',
                                     formatter_class=CustomFormatter,
                                     epilog='''Available environment variables: HTTP_PROXY, HTTPS_PROXY, CRATES_DL, CRATES_API''')
    parser.add_argument('-i', '--index', help='registry index directory', default='/srv/git/index')
    parser.add_argument('-w', '--crates', help='crates directory', default='/srv/www/crates')
    parser.add_argument('-d', '--dbpath', help='database file path', default=None)
    parser.add_argument('-f', '--logfile', help='log file path', default=None)
    parser.add_argument('-c', '--checkdb', help='check database for missing crates',
                                           action='store_true')
    parser.add_argument('-v', '--verbose', help='verbose output', action='store_true')

    custom_config = {
        'dl': os.getenv('CRATES_DL'),
        'api': os.getenv('CRATES_API')
    }
    if not any(custom_config.values()):
        custom_config = None

    args = parser.parse_args()

    with CratesMirror(args.index, args.crates, config=custom_config,
                      dbpath=args.dbpath, logfile=args.logfile,
                      debug=args.verbose) as mirror:
        if args.checkdb:
            mirror.findout_missing_crates()
        mirror.update_repo()

if __name__ == '__main__':
    main()
