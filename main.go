package main

import (
	"fmt"
	"log"
	"os"
)

func main() {
	fmt.Println("Hello World!")
	m, err := NewMirror("index", "crates", "", os.Stdout, false)
	if err != nil {
		log.Fatal(err)
	}
	m.Destroy()
}
