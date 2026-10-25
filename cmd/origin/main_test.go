package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestConditionalRequestPrecedence(t *testing.T) {
	oldContentDir := contentDir
	contentDir = t.TempDir()
	t.Cleanup(func() { contentDir = oldContentDir })

	filePath := filepath.Join(contentDir, "asset.txt")
	if err := os.WriteFile(filePath, []byte("content"), 0600); err != nil {
		t.Fatal(err)
	}
	modified := time.Date(2020, time.January, 1, 0, 0, 0, 0, time.UTC)
	if err := os.Chtimes(filePath, modified, modified); err != nil {
		t.Fatal(err)
	}

	serve := func(headers http.Header) *httptest.ResponseRecorder {
		request := httptest.NewRequest(http.MethodGet, "/asset.txt", nil)
		request.Header = headers
		recorder := httptest.NewRecorder()
		fileHandler(recorder, request)
		return recorder
	}

	initial := serve(make(http.Header))
	if initial.Code != http.StatusOK {
		t.Fatalf("initial request status = %d, want %d", initial.Code, http.StatusOK)
	}
	etag := initial.Header().Get("ETag")
	if etag == "" {
		t.Fatal("initial response has no ETag")
	}

	t.Run("mismatching If-None-Match takes precedence", func(t *testing.T) {
		headers := make(http.Header)
		headers.Set("If-None-Match", `"different"`)
		headers.Set("If-Modified-Since", time.Now().Add(24*time.Hour).UTC().Format(http.TimeFormat))
		if got := serve(headers).Code; got != http.StatusOK {
			t.Fatalf("status = %d, want %d", got, http.StatusOK)
		}
	})

	t.Run("matching If-None-Match returns not modified", func(t *testing.T) {
		headers := make(http.Header)
		headers.Set("If-None-Match", etag)
		if got := serve(headers).Code; got != http.StatusNotModified {
			t.Fatalf("status = %d, want %d", got, http.StatusNotModified)
		}
	})

	t.Run("If-Modified-Since alone returns not modified", func(t *testing.T) {
		headers := make(http.Header)
		headers.Set("If-Modified-Since", modified.Format(http.TimeFormat))
		if got := serve(headers).Code; got != http.StatusNotModified {
			t.Fatalf("status = %d, want %d", got, http.StatusNotModified)
		}
	})
}
