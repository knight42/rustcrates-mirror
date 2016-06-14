package mirror

import (
	"database/sql"
	"errors"
	"fmt"
	_ "github.com/mattn/go-sqlite3"
	"io"
	"log"
	"os"
	"os/exec"
)

type CratesMirror struct {
	indexDir    string
	cratesDir   string
	downloadURL string
	dbPath      string
	logger      *log.Logger
	verbose     bool
	db          *sql.DB
}

func NewMirror(indexDir string, cratesDir string, dbPath string, logFile io.Writer, debug bool) (*CratesMirror, error) {
	if dbPath == "" {
		dbPath = "crates.db"
	}
	os.MkdirAll(cratesDir, 0755)
	logger := log.New(logFile, "crates: ", log.LstdFlags)
	m := CratesMirror{
		indexDir,
		cratesDir,
		"https://crates.io/api/v1/crates/%s/%s/download",
		dbPath,
		logger,
		debug,
		nil,
	}

	db, err := m.initDB()
	if err != nil {
		return nil, err
	}
	m.db = db

	err = m.initRepo()
	if err != nil {
		return nil, err
	}

	return &m, nil
}

func isExist(path string) bool {
	_, err := os.Stat(path)
	return !os.IsNotExist(err)
}

func isDir(path string) bool {
	f, err := os.Stat(path)
	if err != nil {
		return false
	}
	return f.IsDir()
}

func (self *CratesMirror) initRepo() error {
	info, err := os.Stat(self.indexDir)
	if !os.IsNotExist(err) {
		if !info.IsDir() {
			return errors.New(fmt.Sprintf("%s is not a folder\n", self.indexDir))
		} else {
			d, _ := os.Open(self.indexDir)
			defer d.Close()
			names, _ := d.Readdirnames(0)
			if len(names) > 0 {
				// Directory is not empty
				return nil
			}
		}
	}
	cmd := exec.Command("git", "clone", "https://github.com/rust-lang/crates.io-index", self.indexDir)
	err = cmd.Run()
	if err != nil {
		self.logger.Println("[REPO] Clone finished.")
	}
	return err
}

func (self *CratesMirror) initDB() (*sql.DB, error) {

	if isExist(self.dbPath) {
		return sql.Open("sqlite3", self.dbPath)
	}
	self.logger.Fatal(isExist("/tmp"))
	db, err := sql.Open("sqlite3", self.dbPath)
	if err != nil {
		return nil, err
	}

	sqlStmt := `
	CREATE TABLE crate(
		id integer primary key,
		name text,
		version text,
		checksum text,
		yanked integer default 0,
		downloaded integer default 0,
		forbidden integer default 0,
		last_update text
	);
	CREATE UNIQUE INDEX crate_index ON crate(name, version);
	CREATE TABLE update_history (commit_id text, timestamp text);
	CREATE UNIQUE INDEX commit_index ON update_history(commit_id);
	`
	_, err = db.Exec(sqlStmt)
	if err != nil {
		return nil, err
	}
	self.logger.Println("[DATABASE] Succeed!")
	return db, nil
}

func (self *CratesMirror) Destroy() {
	self.db.Close()
}
