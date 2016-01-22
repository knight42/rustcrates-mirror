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
    from tpool import ThreadPoolExecutor


def lmap(f, *args):
    list(map(f, *args))


class CratesMirror(object):
    """

    :param indexdir: the path of registry index directory
    :param cratesdir: the path of directory which contains local crates
    :param config: dictinoary of settings that overrides the default. See `config.json` in your indexDir
    :param proxy: dictionary of proxy config used in requests.get. See also 'http://docs.python-requests.org/en/latest/user/advanced/#proxies'
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

    def __init__(self, indexdir, cratesdir, config=None, proxy=None, debug=False):

        self.logger = logging.getLogger(type(self).__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] <line: %(lineno)d> %(levelname)s: %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        self.proxy = proxy
        self.downloadURL = 'https://crates.io/api/v1/crates/{name}/{version}/download'
        self.indexDir = indexdir
        self.cratesDir = cratesdir
        self.config = config
        self.configPath = os.path.join(self.indexDir, 'config.json')
        self._session = requests.Session()

        if not os.path.isdir(self.cratesDir):
            os.makedirs(self.cratesDir)

        if not os.listdir(self.cratesDir):
            self._bare = True
        else:
            self._bare = False

        dbpath = os.path.join(os.getcwd(), "crates.db")
        self.conn = self.initialize_db(dbpath)
        self.cursor = self.conn.cursor()

        self.repo = self.initialize_repo()

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

        if not os.path.isdir(self.indexDir):
            self.logger.warning('Cloning from GitHub, which may take a while.')
            git.Repo.clone_from('https://github.com/rust-lang/crates.io-index', self.indexDir)
        return git.Repo(self.indexDir)

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
                self.logger.error("Unknown data in %s: %s", fp, line)
            else:
                self.logger.debug('Load %s, %s, %s, %s',
                                  crate["name"], crate["vers"],
                                  crate["cksum"], int(crate["yanked"]))
                crates.append((crate["name"], crate["vers"],
                               crate["cksum"], int(crate["yanked"])))

        try:
            self.cursor.executemany(sql, crates)
        except Exception as e:
            self.logger.error(e)
            return False
        else:
            self.conn.commit()
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

        self.cursor.execute("SELECT count(id) FROM crate;")
        if not force and self.cursor.fetchone()[0] != 0:
            # info already loaded
            return

        for root, dirs, files in os.walk(self.indexDir):
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
        for root, dirs, files in os.walk(self.cratesDir):
            for f in files:
                if not pat.search(f):
                    self.logger.error('Failed to extract name and version from %s', f)
                    continue
                name, vers = pat.search(f).groups()
                try:
                    self.cursor.execute("UPDATE crate SET downloaded = ?, last_update = ? WHERE name = ? AND version = ?", (1, datetime.now(), name, vers))
                except Exception as e:
                    self.logger.error(e)
                else:
                    self.logger.debug('Info of %s-%s updated', name, vers)
                    self.conn.commit()

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
                dlfile = self._session.get(url, timeout=30, proxies=self.proxy)
            except Exception as e:
                self.logger.error(e)
                return False, None
            if dlfile.status_code == 403:
                return False, True

            filehash = hashlib.sha256(dlfile.content).hexdigest()
            if filehash == cksum:
                with open(fp, 'wb') as save:
                    save.write(dlfile.content)
                return True, False
            return False, False

        def _prepare(name, vers, cksum):

            self.logger.debug('Processing %s-%s', name, vers)
            if not cksum:
                self.logger.error('Empty checksum in database: %s-%s', name, vers)
                return (None, None)

            pardir = os.path.join(self.cratesDir, name)
            try:
                os.makedirs(pardir)
            except:
                # directory already exists
                pass
            fp = os.path.join(pardir, '{}-{}.crate'.format(name, vers))
            url = self.downloadURL.format(name=name, version=vers)
            return (url, fp)

        def retrive_crate(name, vers, cksum):

            url, fp = _prepare(name, vers, cksum)

            if not all((url, fp)):
                return

            sql = "UPDATE crate SET {column} = ?, last_update = ? WHERE name = ? AND version = ?"
            downloaded, forbidden = dl_executor(url, cksum, fp)

            try:
                if forbidden:
                    self.cursor.execute(sql.format(column="forbidden"),
                                        (1, datetime.now(), name, vers))
                    self.logger.warning('%s-%s is forbidden', name, vers)
                else:
                    self.cursor.execute(sql.format(column="downloaded"),
                                        (int(downloaded), datetime.now(), name, vers))
                    self.logger.info('Successfully download %s-%s' if downloaded
                                     else 'Failed to download %s-%s', name, vers)
            except Exception as e:
                self.logger.error(e)


        def retrive_crate_multithread(info):

            def wrapped(t):

                url, fp = _prepare(*t)
                if not all((url, fp)):
                    return
                cksum = t[2]
                dl_executor(url, cksum, fp)

            with ThreadPoolExecutor(cpu_count() * 3) as pool:
                pool.map(wrapped, info)
                pool.shutdown(wait=True)

            self.load_downloaded_crates()


        cursor = self.conn.cursor()
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
            if list(self.repo.iter_commits('origin/master..master')):
                # local branch is ahead of origin/master
                self.repo.head.reset('origin/master')

        def commit_custom_config():
            if not self.config:
                return
            with open(self.configPath, 'w') as save:
                json.dump(self.config, save, indent=4)
            self.repo.index.add([self.configPath])
            self.repo.index.commit('point to local server')

        self.cursor.execute("SELECT commit_id FROM update_history ORDER BY datetime(timestamp) DESC LIMIT 1")
        last_update = self.cursor.fetchone()
        if not last_update:
            # bare repo
            reset_head()
            self.retrive_crates()
            self.cursor.execute("INSERT OR REPLACE INTO update_history (commit_id, timestamp) VALUES (?, ?)",
                                (str(self.repo.commit()), datetime.now()))
            self.conn.commit()
            commit_custom_config()
            return
        else:
            last_update = last_update[0]

        self.logger.debug("Last commit: %s", last_update)

        reset_head()

        origin = self.repo.remotes['origin']
        self.logger.info("Pulling from remote...")
        origin.pull()
        self.logger.debug("Lastest commit: %s", self.repo.commit())
        deletedList = []
        newfileList = []
        modifiedList = []
        diffs = self.repo.commit(last_update).diff(self.repo.commit())
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

        self.logger.debug('deleted: %s', deletedList)
        self.logger.debug('newfiles: %s', newfileList)
        self.logger.debug('modified: %s', modifiedList)
        if deletedList:
            self.cursor.executemany("DELETE FROM crate WHERE name = ?", deletedList)
            self.conn.commit()

        lmap(self.load_crate, newfileList)
        lmap(functools.partial(self.load_crate, latest_only=True), modifiedList)

        self.retrive_crates()

        lmap(shutil.rmtree, [os.path.join(self.cratesDir, f[0]) for f in deletedList])

        self.cursor.execute("INSERT OR REPLACE INTO update_history (commit_id, timestamp) VALUES (?, ?)",
                            (str(self.repo.commit()), datetime.now()))

        commit_custom_config()

        self.conn.commit()

    def __enter__(self):

        self.load_crates_from_index()
        return self

    def __exit__(self, exc_type, exc_value, tb):

        self.conn.close()

if __name__ == '__main__':

    indexDir = '/srv/git/index'
    cratesDir = '/srv/www/crates'
    config = {'dl': 'https://crates.mirrors.ustc.edu.cn/api/v1/crates',
              'api': 'https://crates.io'}
    with CratesMirror(indexDir, cratesDir, config, debug=True) as mirror:
        mirror.update_repo()

# vim:set et sw=4 ts=4:
