package main

import (
	"crypto/md5"
	"fmt"
	"io"
	"log"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

var (
	contentDir = "./sample-content"
	port       = "9000"
)

func main() {
	if dir := os.Getenv("CONTENT_DIR"); dir != "" {
		contentDir = dir
	}
	if p := os.Getenv("PORT"); p != "" {
		port = p
	}

	log.Printf("Starting Origin Server on port %s, serving from %s", port, contentDir)

	http.HandleFunc("/", fileHandler)

	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Origin Server failed to start: %v", err)
	}
}

func fileHandler(w http.ResponseWriter, r *http.Request) {
	log.Printf("Origin received request: %s %s", r.Method, r.URL.Path)

	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	// Clean path to prevent directory traversal
	cleanPath := filepath.Clean(r.URL.Path)
	if strings.HasPrefix(cleanPath, "..") {
		http.Error(w, "Forbidden", http.StatusForbidden)
		return
	}

	filePath := filepath.Join(contentDir, cleanPath)

	// If a directory is requested, attempt to serve index.html
	fileInfo, err := os.Stat(filePath)
	if err == nil && fileInfo.IsDir() {
		filePath = filepath.Join(filePath, "index.html")
		fileInfo, err = os.Stat(filePath)
	}

	if err != nil {
		if os.IsNotExist(err) {
			log.Printf("File not found: %s", filePath)
			http.NotFound(w, r)
		} else {
			log.Printf("Error accessing file %s: %v", filePath, err)
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		}
		return
	}

	file, err := os.Open(filePath)
	if err != nil {
		log.Printf("Error opening file %s: %v", filePath, err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	defer file.Close()

	// Read content to calculate ETag
	content, err := io.ReadAll(file)
	if err != nil {
		log.Printf("Error reading file %s: %v", filePath, err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	// Compute ETag
	etag := fmt.Sprintf("\"%x\"", md5.Sum(content))
	lastModified := fileInfo.ModTime().UTC().Round(time.Second)

	// Set Headers
	w.Header().Set("Cache-Control", "public, max-age=3600")
	w.Header().Set("ETag", etag)
	w.Header().Set("Last-Modified", lastModified.Format(http.TimeFormat))

	// Detect Content-Type
	ext := filepath.Ext(filePath)
	contentType := mime.TypeByExtension(ext)
	if contentType == "" {
		contentType = http.DetectContentType(content)
	}
	w.Header().Set("Content-Type", contentType)

	// Handle Conditional Request (If-None-Match)
	ifNoneMatch := r.Header.Get("If-None-Match")
	if ifNoneMatch != "" && (ifNoneMatch == etag || ifNoneMatch == "*") {
		w.WriteHeader(http.StatusNotModified)
		return
	}

	// Handle Conditional Request (If-Modified-Since)
	ifModifiedSinceHeader := r.Header.Get("If-Modified-Since")
	if ifModifiedSinceHeader != "" {
		if t, err := time.Parse(http.TimeFormat, ifModifiedSinceHeader); err == nil {
			if !lastModified.After(t) {
				w.WriteHeader(http.StatusNotModified)
				return
			}
		}
	}

	// Return response
	w.WriteHeader(http.StatusOK)
	if r.Method == http.MethodGet {
		w.Write(content)
	}
}
