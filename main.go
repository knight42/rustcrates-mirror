package main

import (
	"bufio"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"path"
	"runtime"
	"strings"
)

func isExist(p string) bool {
	_, err := os.Stat(p)
	return !os.IsNotExist(err)
}

func LazyServer(addr string) {
	http.HandleFunc("/gc", func(w http.ResponseWriter, r *http.Request) {
		runtime.GC()
	})

	local := os.Getenv("CRATES_DIR")
	if len(local) == 0 {
		local = "/tmp/crates"
	}

	errLog := log.New(os.Stderr, "", log.LstdFlags)
	prefix := "/api/v1/crates/"
	http.HandleFunc(prefix, func(w http.ResponseWriter, r *http.Request) {
		fmt.Printf("goroutines start: %d\n", runtime.NumGoroutine())

		//log.Println(r.URL.Path)

		p := strings.TrimPrefix(r.URL.Path, prefix)
		compo := strings.Split(p, "/")
		if len(compo) != 3 {
			http.Error(w, "Bad request", http.StatusBadRequest)
			errLog.Println(r.URL.Path)
			return
		} else if compo[2] != "download" {
			http.Error(w, "Bad request", http.StatusBadRequest)
			errLog.Println(r.URL.Path)
			return
		}

		name, version := compo[0], compo[1]
		localStorage := path.Join(local, name, fmt.Sprintf("%s@%s", name, version))

		if isExist(localStorage) {
			in, err := os.Open(localStorage)
			if err != nil {
				http.Error(w, "Failed to open file", http.StatusInternalServerError)
				errLog.Println(err)
				return
			}
			defer in.Close()
			bufin := bufio.NewReader(in)
			_, err = bufin.WriteTo(w)
			if err != nil {
				errLog.Println(err)
			}
			return
		}

		d := path.Join(local, name)
		if !isExist(d) {
			os.MkdirAll(d, 0755)
		}

		url := fmt.Sprintf("https://crates.io%s", r.URL.Path)
		resp, err := http.Get(url)
		ct := resp.Header.Get("Content-Type")
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			errLog.Println(err)
			return
		} else if strings.Contains(ct, "json") {
			http.Error(w, "crate or version not found", http.StatusBadRequest)
			errLog.Println(url, "crate or version not found")
			return
		} else if resp.StatusCode != http.StatusOK {
			http.Error(w, resp.Status, resp.StatusCode)
			errLog.Println(url, resp.Status)
			return
		}

		defer resp.Body.Close()
		f, err := os.Create(localStorage)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			errLog.Println(err)
			return
		}
		defer f.Close()
		ws := io.MultiWriter(w, f)
		data, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			errLog.Println(err)
		}
		_, err = ws.Write(data)
		if err != nil {
			os.Remove(localStorage)
			errLog.Println(err)
		}
	})
	log.Printf("Listening on %s\n", addr)
	errLog.Fatal(http.ListenAndServe(addr, nil))
}

func main() {
	LazyServer(":8080")
}
