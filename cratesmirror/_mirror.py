#!/usr/bin/python3 -O
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, with_statement

import git
import requests

import os
import re
import json
import sqlite3
import shutil
import functools
import hashlib
import logging
from datetime import datetime
from multiprocessing import cpu_count

try:
    from concurrent.futures import ThreadPoolExecutor
except ImportError:
    from ._tpool import ThreadPoolExecutor


def lmap(f, *args):
    list(map(f, *args))

_current_dir = os.path.dirname(os.path.realpath(__file__))


class CratesMirror(object):
    """

    :param indexdir: the path of registry index directory
    :param cratesdir: the path of directory which contains local crates
    :param config: dictinoary of settings that overrides the default. See `config.json` in your indexDir
    :param proxy: dictionary of proxy config used in requests.get. See also 'http://docs.python-requests.org/en/latest/user/advanced/#proxies'
    :param dbpath: path of database file. <current_dir>/crates.db by default
    :param logfile: path of log file. Write to stdout by default
    :param debug: verbose output

    Usage::

        proxies = {
          "http": "http://10.10.1.10:3128",
          "https": "http://10.10.1.10:1080",
        }
        index = '/srv/git/index'
        crates = '/srv/www/crates'
        config = {'dl': 'https://crates.mirrors.ustc.edu.cn/api/v1/crates',
                  'api': 'https://crates.io'}

        with CratesMirror(index, crates, config=config, proxy=proxies, debug=True) as mirror:
            mirror.update_repo()

    """

    def __init__(self, indexdir, cratesdir, config=None,
                 dbpath=None, logfile=None,
                 proxy=None, debug=False):

        self._logger = logging.getLogger(type(self).__name__)
        if debug:
            self._logger.setLevel(logging.DEBUG)
        else:
            self._logger.setLevel(logging.INFO)

        if logfile:
            ch = logging.FileHandler(logfile)
        else:
            ch = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] <line: %(lineno)d> %(levelname)s: %(message)s')
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

        self._proxy = proxy
        self._downloadURL = 'https://crates.io/api/v1/crates/{name}/{version}/download'
        self._index_dir = indexdir
        self._crates_dir = cratesdir
        self._config = config
        self._configPath = os.path.join(self._index_dir, 'config.json')
        self._session = requests.Session()

        if not os.path.isdir(self._crates_dir):
            os.makedirs(self._crates_dir)

        if not os.listdir(self._crates_dir):
            self._bare = True
        else:
            self._bare = False

        if dbpath is None:
            dbpath = os.path.join(os.getcwd(), "crates.db")
        self._conn = self.initialize_db(dbpath)
        self._cursor = self._conn.cursor()

        self._repo = self.initialize_repo()

    def initialize_db(self, dbpath):
        """
        Initialize local database.

        :param dbpath: path of local database
        :returns: sqlite3.Connection

        """

        if os.path.exists(dbpath):
            return sqlite3.connect(dbpath)

        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE crate (
                              id integer primary key,
                              name text,
                              version text,
                              checksum text,
                              yanked integer default 0,
                              downloaded integer default 0,
                              forbidden integer default 0,
                              last_update text
                          )""")
        cursor.execute("""CREATE UNIQUE INDEX crate_index ON crate(name, version)""")
        cursor.execute("""CREATE TABLE update_history (
                              commit_id text,
                              timestamp text
                          )""")
        cursor.execute("""CREATE UNIQUE INDEX commit_index ON update_history(commit_id)""")
        conn.commit()
        return conn

    def initialize_repo(self):
        """
        Initialize a local github repository. If nonexistent, clone it from remote.

        :param: None
        :returns: git.Repo

        """

        if not os.path.isdir(self._index_dir):
            self._logger.warning('Cloning from GitHub, which may take a while.')
            git.Repo.clone_from('https://github.com/rust-lang/crates.io-index', self._index_dir)
        return git.Repo(self._index_dir)

    def load_crate(self, fp, latest_only=False):
        """
        Load information of one crate into database

        :param fp: file path string
        :param latest_only: if set to be True, only the latest version of crate is considered
        :returns: True if success, otherwise False

        """

        def gen_lines():
            with open(fp, 'r') as json_file:
                if latest_only:
                    last_line = ''
                    for line in json_file:
                        if line.strip():
                            last_line = line
                    yield last_line
                else:
                    # yield from filter(lambda x: x.strip(), json_file)
                    for line in json_file:
                        if line.strip():
                            yield line

        crates = []
        sql = "INSERT OR REPLACE INTO crate (name, version, checksum, yanked) VALUES (?, ?, ?, ?);"
        for line in gen_lines():
            try:
                crate = json.loads(line)
            except:
                self._logger.error("Unknown data in %s: %s", fp, line)
            else:
                self._logger.debug('Load %s, %s, %s, %s',
                                  crate["name"], crate["vers"],
                                  crate["cksum"], int(crate["yanked"]))
                crates.append((crate["name"], crate["vers"],
                               crate["cksum"], int(crate["yanked"])))

        try:
            self._cursor.executemany(sql, crates)
        except Exception as e:
            self._logger.error(e)
            return False
        else:
            self._conn.commit()
            return True

    def load_crates_from_index(self, force=False):
        """
        If the `crate` table in database is empty
            then traverse the local index dir recursively and load all crates,
        else
            return

        :param force: if set to be True, override ALL the information in `crate` table
        :returns: None

        """

        self._cursor.execute("SELECT count(id) FROM crate;")
        if not force and self._cursor.fetchone()[0] != 0:
            # info already loaded
            return

        for root, dirs, files in os.walk(self._index_dir):
            if '.git' in dirs:
                dirs.remove('.git')

            lmap(self.load_crate, [os.path.join(root, f) for f in files if f != 'config.json'])

    def load_downloaded_crates(self):
        """
        WARNING: Only after loading all infomation of crates into database should this function be called.
        Set local crates as downloaded.

        :param: None
        :returns: None

        """

        pat = re.compile('(.+)-(\d+\..+).crate')
        for root, dirs, files in os.walk(self._crates_dir):
            for f in files:
                if not pat.search(f):
                    self._logger.error('Failed to extract name and version from %s', f)
                    continue
                name, vers = pat.search(f).groups()
                try:
                    self._cursor.execute("UPDATE crate SET downloaded = ?, last_update = ? WHERE name = ? AND version = ?", (1, datetime.now(), name, vers))
                except Exception as e:
                    self._logger.error(e)
                else:
                    self._logger.debug('Info of %s-%s updated', name, vers)
                    self._conn.commit()

    def retrive_crates(self):
        """
        Download all not-downloaded and not-forbidden crates.
        Information is grasped from local database.

        :param: None
        :returns: None

        """

        def dl_executor(url, cksum, fp):
            """
            Download and verify the checksum of file

            :param url: URL of the crate
            :param cksum: the correct checksum of crate
            :param fp: path to save crate
            :returns: (downloaded, valid), both are boolean

            """

            if not self._bare and os.path.isfile(fp):
                with open(fp, 'rb') as toverify:
                    if hashlib.sha256(toverify.read()).hexdigest() == cksum:
                        return True, None
                    else:
                        os.remove(fp)
                return False, None

            try:
                dlfile = self._session.get(url, timeout=30, proxies=self._proxy)
            except Exception as e:
                self._logger.error(e)
                return False, None
            if dlfile.status_code == 403:
                return False, True

            filehash = hashlib.sha256(dlfile.content).hexdigest()
            if filehash == cksum:
                with open(fp, 'wb') as save:
                    save.write(dlfile.content)
                return True, False
            return False, False

        def prepare(name, vers, cksum):

            self._logger.debug('Processing %s-%s', name, vers)
            if not cksum:
                self._logger.error('Empty checksum in database: %s-%s', name, vers)
                return (None, None)

            pardir = os.path.join(self._crates_dir, name)
            try:
                os.makedirs(pardir)
            except:
                # directory already exists
                pass
            fp = os.path.join(pardir, '{}-{}.crate'.format(name, vers))
            url = self._downloadURL.format(name=name, version=vers)
            return (url, fp)

        def retrive_crate(name, vers, cksum):

            url, fp = prepare(name, vers, cksum)

            if not all((url, fp)):
                return

            sql = "UPDATE crate SET {column} = ?, last_update = ? WHERE name = ? AND version = ?"
            downloaded, forbidden = dl_executor(url, cksum, fp)

            try:
                if forbidden:
                    self._cursor.execute(sql.format(column="forbidden"),
                                        (1, datetime.now(), name, vers))
                    self._logger.warning('%s-%s is forbidden', name, vers)
                else:
                    self._cursor.execute(sql.format(column="downloaded"),
                                        (int(downloaded), datetime.now(), name, vers))
                    self._logger.info('Successfully download %s-%s' if downloaded
                                     else 'Failed to download %s-%s', name, vers)
            except Exception as e:
                self._logger.error(e)

        def retrive_crate_multithread(info):

            def wrapped(t):

                url, fp = prepare(*t)
                if not all((url, fp)):
                    return
                cksum = t[2]
                dl_executor(url, cksum, fp)

            with ThreadPoolExecutor(cpu_count() * 3) as pool:
                pool.map(wrapped, info)
                pool.shutdown(wait=True)

            self.load_downloaded_crates()

        cursor = self._conn.cursor()
        cursor.execute("SELECT name, version, checksum FROM crate WHERE downloaded = 0 AND forbidden = 0")

        if self._bare:
            retrive_crate_multithread(cursor)
            self._bare = False
        else:
            lmap(lambda t: retrive_crate(*t), cursor)

    def update_repo(self):
        """
        Sync with crates.io-index and update local crates

        :param: None
        :returns: None

        """

        def reset_head():
            if list(self._repo.iter_commits('origin/master..master')):
                # local branch is ahead of origin/master
                self._repo.head.reset('origin/master')

        def commit_custom_config():
            if not self._config:
                return
            with open(self._configPath, 'w') as save:
                json.dump(self._config, save, indent=4)
            self._repo.index.add([self._configPath])
            self._repo.index.commit('point to local server')

        self._cursor.execute("SELECT commit_id FROM update_history ORDER BY datetime(timestamp) DESC LIMIT 1")
        last_update = self._cursor.fetchone()
        if not last_update:
            # bare repo
            reset_head()
            self.retrive_crates()
            self._cursor.execute("INSERT OR REPLACE INTO update_history (commit_id, timestamp) VALUES (?, ?)",
                                (str(self._repo.commit()), datetime.now()))
            self._conn.commit()
            commit_custom_config()
            return
        else:
            last_update = last_update[0]

        self._logger.debug("Last commit: %s", last_update)

        reset_head()

        origin = self._repo.remotes['origin']
        self._logger.info("Pulling from remote...")
        origin.pull()
        self._logger.debug("Lastest commit: %s", self._repo.commit())
        deletedList = []
        newfileList = []
        modifiedList = []
        diffs = self._repo.commit(last_update).diff(self._repo.commit())
        for diff in diffs:
            if diff.new_file:
                newfileList.append(diff.b_blob.abspath)
            elif diff.renamed:
                deletedList.append((diff.a_blob.name, ))
                newfileList.append(diff.b_blob.abspath)
            elif diff.deleted_file:
                deletedList.append((diff.a_blob.name, ))
            else:
                modifiedList.append(diff.a_blob.abspath)

        self._logger.debug('deleted: %s', deletedList)
        self._logger.debug('newfiles: %s', newfileList)
        self._logger.debug('modified: %s', modifiedList)
        if deletedList:
            self._cursor.executemany("DELETE FROM crate WHERE name = ?", deletedList)
            self._conn.commit()

        lmap(self.load_crate, newfileList)
        lmap(functools.partial(self.load_crate, latest_only=True), modifiedList)

        self.retrive_crates()

        lmap(shutil.rmtree, [os.path.join(self._crates_dir, f[0]) for f in deletedList])

        self._cursor.execute("INSERT OR REPLACE INTO update_history (commit_id, timestamp) VALUES (?, ?)",
                            (str(self._repo.commit()), datetime.now()))

        commit_custom_config()

        self._conn.commit()

    def __enter__(self):

        self.load_crates_from_index()
        return self

    def __exit__(self, exc_type, exc_value, tb):

        self._conn.close()
        return False

if __name__ == '__main__':

    index_dir = '/srv/git/index'
    crates_dir = '/srv/www/crates'
    config = {'dl': 'https://crates.mirrors.ustc.edu.cn/api/v1/crates',
              'api': 'https://crates.io'}
    logfile = os.path.join('/var/log/crates-mirror', 'debug.log')
    dbpath = os.path.join('/var/lib/crates-mirror', 'crates.db')
    with CratesMirror(index_dir, crates_dir, dbpath=dbpath, logfile=logfile, config=config, debug=True) as mirror:
        mirror.update_repo()

# vim:set sta et sw=4 ts=4:
