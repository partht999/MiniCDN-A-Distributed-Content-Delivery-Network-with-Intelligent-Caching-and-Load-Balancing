package main

import (
	"mini-cdn/pkg/cache"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestExpiredEntryIsConditionallyRevalidated(t *testing.T) {
	oldURL, oldCache := originURL, cdnCache
	defer func() { originURL, cdnCache = oldURL, oldCache }()
	cdnCache = cache.NewCache()
	cdnCache.Set("/asset", 200, []byte("retained"), http.Header{"Etag": []string{`"v1"`}, "Cache-Control": []string{"public, max-age=1"}}, time.Hour)
	entry, _ := cdnCache.Peek("/asset")
	entry.Expiration = time.Now().Add(-time.Hour)
	conditional := false
	origin := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conditional = r.Header.Get("If-None-Match") == `"v1"`
		w.Header().Set("Cache-Control", "public, max-age=60")
		w.WriteHeader(304)
	}))
	defer origin.Close()
	originURL = origin.URL
	rec := httptest.NewRecorder()
	handleProxy(rec, httptest.NewRequest("GET", "/asset", nil))
	if !conditional || rec.Code != 200 || rec.Body.String() != "retained" || rec.Header().Get("X-Cache") != "REVALIDATED" {
		t.Fatalf("bad validation: %d %s %v", rec.Code, rec.Body.String(), conditional)
	}
	if _, ok := cdnCache.Peek("/asset"); !ok {
		t.Fatal("validation did not renew freshness")
	}
}

func TestOversizedResponseStreamsWithoutCaching(t *testing.T) {
	oldURL, oldCache, oldMax := originURL, cdnCache, maxObjectBytes
	defer func() { originURL, cdnCache, maxObjectBytes = oldURL, oldCache, oldMax }()
	cdnCache = cache.NewCache()
	maxObjectBytes = 4
	origin := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "public, max-age=60")
		w.Write([]byte("123456789"))
	}))
	defer origin.Close()
	originURL = origin.URL
	rec := httptest.NewRecorder()
	handleProxy(rec, httptest.NewRequest("GET", "/large", nil))
	if rec.Body.String() != "123456789" {
		t.Fatal("stream truncated")
	}
	if _, ok := cdnCache.Peek("/large"); ok {
		t.Fatal("oversized response cached")
	}
}

func TestPrefixPurgeIncludesQueryVariants(t *testing.T) {
	oldCache := cdnCache
	defer func() { cdnCache = oldCache }()
	cdnCache = cache.NewCache()
	for _, key := range []string{"/assets/a?q=1", "/assets/b", "/other"} {
		cdnCache.Set(key, 200, []byte("x"), nil, time.Minute)
	}
	rec := httptest.NewRecorder()
	handlePurge(rec, httptest.NewRequest("POST", "/internal/purge", strings.NewReader(`{"prefixes":["/assets/"]}`)))
	if rec.Code != 200 || cdnCache.Size() != 1 {
		t.Fatal("prefix purge failed")
	}
}
