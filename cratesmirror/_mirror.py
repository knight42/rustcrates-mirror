#!/usr/bin/python -O
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, with_statement

import git
import requests

import os
import re
import json
import sqlite3
import shutil
import hashlib
import logging
import threading
import contextlib
from datetime import datetime
from multiprocessing import cpu_count

try:
    from concurrent.futures import ThreadPoolExecutor
except ImportError:
    from ._tpool import ThreadPoolExecutor

from ._utils import walk_git, gen_lines, foreach, TaskQueue

class MyProgressPrinter(git.RemoteProgress):

    def update(self, op_code, cur_count, max_count=None, message=''):
        if(op_code == git.RemoteProgress.RECEIVING):
            if (cur_count != max_count):
                print('Current progress: {:.2f}%'.format(cur_count / (max_count or 100.0) * 100), end='\r')
            else:
                print('')

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
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

        self._proxy = proxy
        self._downloadURL = 'https://crates.io/api/v1/crates/{name}/{version}/download'
        self._index_dir = indexdir
        self._crates_dir = cratesdir
        self._config_path = os.path.join(indexdir, 'config.json')
        self._session = requests.Session()

        DEFAULT_CONFIG = {'api': 'https://crates.io', 'dl': 'https://crates.io/api/v1/crates'}
        if config is not None:
            config['api'] = config.get('api', None) or DEFAULT_CONFIG['api']
            config['dl'] = config.get('dl', None) or DEFAULT_CONFIG['dl']
            if config == DEFAULT_CONFIG:
                config = None
        self._config = config

        if not os.path.isdir(self._crates_dir):
            os.makedirs(self._crates_dir)

        if dbpath is None:
            dbpath = os.path.join(os.getcwd(), "crates.db")
        elif os.path.isdir(dbpath):
            dbpath = os.path.join(dbpath, "crates.db")
        self._dbpath = dbpath
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
        self._logger.info('[DATABASE] Creating `crate` and `update_history` table ...');
        cursor.execute("""CREATE TABLE crate (
                              id integer primary key,
                              name text,
                              version text,
                              checksum text,
                              yanked integer default 0,
                              downloaded integer default 0,
                              forbidden integer default 0,
                              last_update text
                          );""")
        cursor.execute("""CREATE UNIQUE INDEX crate_index ON crate(name, version);""")
        cursor.execute("""CREATE TABLE update_history (
                              commit_id text,
                              timestamp text
                          );""")
        cursor.execute("""CREATE UNIQUE INDEX commit_index ON update_history(commit_id);""")
        conn.commit()
        self._logger.info('[DATABASE] Succeed!');
        return conn

    def initialize_repo(self):
        """
        Initialize a local github repository. If nonexistent, clone it from remote.

        :param: None
        :returns: git.Repo

        """

        if os.path.isdir(self._index_dir) and os.listdir(self._index_dir):
            pass
        else:
            self._logger.warning('[REPO] Cloning from GitHub, which may take a while.')
            git.Repo.clone_from('https://github.com/rust-lang/crates.io-index',
                                self._index_dir,
                                progress=MyProgressPrinter())
            self._logger.info('[REPO] Clone finished.')
        return git.Repo(self._index_dir)

    def load_crate(self, fp=None, data=None):
        """
        Load information of one crate into database

        :param fp: file path
        :param data: specify the data source(lines generator)
        :returns: True if success, otherwise False

        """

        if fp:
            data = gen_lines(fp)
        elif data is None:
            raise ValueError('Need to provide data')

        def crates():
            for line in data:
                try:
                    crate = json.loads(line)
                except ValueError:
                    self._logger.error("[CRATE] Unknown data: %s", line)
                else:
                    self._logger.info('[DATABASE] Load %s, %s, %s, %s',
                                      crate["name"], crate["vers"],
                                      crate["cksum"], int(crate["yanked"]))
                    yield (crate["name"], crate["vers"],
                           crate["cksum"], int(crate["yanked"]))

        return self._insert_db(crates());

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

        foreach(self.load_crate, walk_git(self._index_dir))

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
                    self._logger.error('[CRATE] Failed to extract name and version from %s', f)
                    continue
                name, vers = pat.search(f).groups()
                try:
                    self._cursor.execute("UPDATE crate SET downloaded = ?, last_update = ? WHERE name = ? AND version = ?", (1, datetime.now(), name, vers))
                except Exception as e:
                    self._logger.error(e)
                else:
                    self._logger.info('[DATABASE] Info of %s-%s updated', name, vers)
                    self._conn.commit()

    def retrive_crates(self):
        """
        Download all not-downloaded and not-forbidden crates.
        Information is grasped from local database.

        :param: None
        :returns: True if all downloads succeed, otherwise False

        """

        self._logger.info('[CRATE] Downloading crates from crates.io...')

        self._cursor.execute("SELECT name, version, checksum FROM crate WHERE downloaded = 0 AND forbidden = 0;")
        results = TaskQueue()
        cnt = {'success': 0, 'fail': 0}

        def save_result():
            '''
            Update database according to the download process
            '''

            sql = "UPDATE crate SET {column} = ?, last_update = ? WHERE name = ? AND version = ?;"
            with contextlib.closing(sqlite3.connect(self._dbpath)) as conn:
                cursor = conn.cursor()
                for item in results:
                    name, vers, downloaded, forbidden = item
                    try:
                        if forbidden:
                            cursor.execute(sql.format(column="forbidden"),
                                          (1, datetime.now(), name, vers))
                            self._logger.warning('[UPSTREAM] %s-%s is forbidden', name, vers)
                        else:
                            cursor.execute(sql.format(column="downloaded"),
                                          (int(downloaded), datetime.now(), name, vers))
                    except Exception as e:
                        self._logger.error(e)
                    else:
                        if downloaded:
                            self._logger.info('[CRATE] Successfully download %s-%s', name, vers)
                            cnt['success'] += 1
                        else:
                            self._logger.error('[CRATE] Failed to download %s-%s', name, vers)
                            cnt['fail'] += 1
                    results.task_done()
                    conn.commit()

        def worker(t):
            '''
            Worker threads to download crates

            :param: (name, version, checksum)
            :returns: None
            '''

            name, vers, cksum = t
            self._logger.debug('Processing %s-%s', name, vers)
            if not cksum:
                return self._logger.error('[DATABASE] Empty checksum of %s-%s', name, vers)
            add_result = lambda downloaded, forbidden: results.put((name, vers, downloaded, forbidden))

            pardir = os.path.join(self._crates_dir, name)
            if not os.path.isdir(pardir):
                os.makedirs(pardir)
            fp = os.path.join(pardir, '{}-{}.crate'.format(name, vers))
            url = self._downloadURL.format(name=name, version=vers)

            if os.path.isfile(fp):
                with open(fp, 'rb') as toverify:
                    if hashlib.sha256(toverify.read()).hexdigest() == cksum:
                        return add_result(True, False)
                    else:
                        os.remove(fp)

            try:
                # requests will automatically decompresses gzip-encoded responses
                resp = self._session.get(url, timeout=30, proxies=self._proxy, stream=True)
            except Exception as e:
                self._logger.error(e)
                return add_result(False, False)
            if resp.status_code == 403:
                return add_result(False, True)

            filehash = hashlib.sha256(resp.raw.data).hexdigest()
            if filehash == cksum:
                with open(fp, 'wb') as save:
                    save.write(resp.raw.data)
                return add_result(True, False)
            return add_result(False, False)

        consumer = threading.Thread(target=save_result)
        with ThreadPoolExecutor(cpu_count() * 3) as pool:
            consumer.start()
            pool.map(worker, self._cursor)
            pool.shutdown(wait=True)
        results.put(None)

        consumer.join()
        self._logger.info('[CRATE] Finished. %s succeeded, %s failed.', cnt['success'], cnt['fail'])
        if cnt['fail']:
            return False
        return True

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
            if self._config is None:
                return
            with open(self._config_path, 'w') as save:
                json.dump(self._config, save, indent=4)
            self._repo.index.add(['config.json'])
            self._repo.index.commit('point to local server')

        def new_crates(last, latest):
            # no bytes
            for line in filter(lambda s: s.startswith('+{'),
                    self._repo.git.execute(['git', 'diff', '-U0', last, latest]).split(os.linesep)):
                yield line[1:] # skip '+'

        self._cursor.execute("SELECT commit_id FROM update_history ORDER BY datetime(timestamp) DESC LIMIT 1;")
        last_update = self._cursor.fetchone()

        reset_head()

        if not last_update:
            # bare repo
            self.retrive_crates()
            self._cursor.execute("INSERT OR REPLACE INTO update_history (commit_id, timestamp) VALUES (?, ?);",
                                (str(self._repo.commit()), datetime.now()))
            self._conn.commit()
            return commit_custom_config()
        else:
            last_update = last_update[0]

        self._logger.info("[REPO] Updating %s", self._index_dir)
        self._logger.debug("Last commit: %s", last_update)

        origin = self._repo.remotes['origin']
        self._logger.info("[REPO] Pulling from remote...")
        origin.pull()
        latest = str(self._repo.commit())
        self._logger.debug("Lastest commit: %s", latest)

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

        self._logger.info('[REPO]  deleted: %s', deletedList)
        self._logger.info('[REPO] newfiles: %s', newfileList)
        self._logger.info('[REPO] modified: %s', modifiedList)

        if deletedList:
            self._cursor.executemany("DELETE FROM crate WHERE name = ?", deletedList)
            self._conn.commit()
        self.load_crate(data=new_crates(last_update, latest))

        self.retrive_crates()

        foreach(shutil.rmtree, [os.path.join(self._crates_dir, f[0]) for f in deletedList])

        self._cursor.execute("INSERT OR REPLACE INTO update_history (commit_id, timestamp) VALUES (?, ?);",
                            (latest, datetime.now()))

        commit_custom_config()

        self._conn.commit()

        self._logger.info('[REPO] Already up-to-date.')

    def _insert_db(self, crates):

        sql = "INSERT OR REPLACE INTO crate (name, version, checksum, yanked) VALUES (?, ?, ?, ?);"
        try:
            self._cursor.executemany(sql, crates)
        except Exception as e:
            self._logger.error(e)
            return False
        else:
            self._conn.commit()
            return True

    def findout_missing_crates(self):
        """
        Find out missing crates in database

        :param: None
        :returns: None

        """

        query = 'SELECT name FROM crate WHERE name = ? AND version = ?;'
        self._logger.info("[DATABASE] Checking database for missing crates, please be patient...")
        missing = {'cnt': 0}
        def crates():
            # avoid recursive use of cursors
            cursor = self._conn.cursor()
            for fp in walk_git(self._index_dir):
                for line in gen_lines(fp):
                    try:
                        crate = json.loads(line)
                    except ValueError:
                        self._logger.error("[CRATE] Unknown data in %s: %s", fp, line)
                    else:
                        # cannot execute SELECT statements in executemany()
                        cursor.execute(query, (crate['name'], crate['vers']))
                        if not cursor.fetchone():
                            self._logger.error("[DATABASE] Missing crate: %s-%s",
                                               crate['name'], crate['vers'])
                            missing['cnt'] += 1
                            yield (crate['name'], crate['vers'],
                                   crate['cksum'], int(crate['yanked']))
        self._insert_db(crates())
        self._logger.info("[DATABASE] Finished. %s",
                          '{} crates are missing'.format(missing['cnt']))

    def __enter__(self):

        self.load_crates_from_index()
        return self

    def __exit__(self, exc_type, exc_value, tb):

        self._conn.close()
        return False

# vim:set sta et sw=4 ts=4:
