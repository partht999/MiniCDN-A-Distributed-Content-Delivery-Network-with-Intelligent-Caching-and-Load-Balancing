package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"mini-cdn/pkg/cache"
)

func TestParseCacheControl(t *testing.T) {
	tests := []struct {
		name     string
		header   string
		expected time.Duration
	}{
		{
			name:     "empty header returns default TTL",
			header:   "",
			expected: 60 * time.Second,
		},
		{
			name:     "standard max-age",
			header:   "public, max-age=3600",
			expected: 3600 * time.Second,
		},
		{
			name:     "max-age zero",
			header:   "max-age=0",
			expected: 0,
		},
		{
			name:     "no-cache directive",
			header:   "no-cache",
			expected: 0,
		},
		{
			name:     "no-store directive",
			header:   "no-store",
			expected: 0,
		},
		{
			name:     "private directive",
			header:   "private",
			expected: 0,
		},
		{
			name:     "private combined with max-age",
			header:   "private, max-age=3600",
			expected: 0,
		},
		{
			name:     "max-age combined with no-store",
			header:   "max-age=3600, no-store",
			expected: 0,
		},
		{
			name:     "max-age combined with no-cache",
			header:   "max-age=3600, no-cache",
			expected: 0,
		},
		{
			name:     "negative max-age",
			header:   "max-age=-10",
			expected: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := parseCacheControl(tt.header)
			if got != tt.expected {
				t.Errorf("parseCacheControl(%q) = %v; want %v", tt.header, got, tt.expected)
			}
		})
	}
}

func TestZeroTTLCacheRegression(t *testing.T) {
	// Initialize local test cache
	cdnCache = cache.NewCache()
	nodeID = "test-edge"

	// Mock origin server returning no-store, no-cache
	originMock := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-cache, no-store")
		w.Header().Set("Content-Type", "text/plain")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("uncacheable dynamic data"))
	}))
	defer originMock.Close()

	originURL = originMock.URL

	// First request: Cache MISS, fetch from origin
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/dynamic/data", nil)

	handleProxy(rec, req)

	resp := rec.Result()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", resp.StatusCode)
	}
	if resp.Header.Get("X-Cache") != "MISS" {
		t.Errorf("expected X-Cache MISS on first request, got %s", resp.Header.Get("X-Cache"))
	}

	// Verify that the key was NOT inserted into cache
	entry, hit := cdnCache.Get("/dynamic/data")
	if hit || entry != nil {
		t.Fatalf("expected key to NOT be cached for zero-TTL response, but found in cache")
	}

	// Second request: Should still be a Cache MISS, not HIT
	rec2 := httptest.NewRecorder()
	req2 := httptest.NewRequest(http.MethodGet, "/dynamic/data", nil)

	handleProxy(rec2, req2)

	resp2 := rec2.Result()
	if resp2.Header.Get("X-Cache") != "MISS" {
		t.Errorf("expected X-Cache MISS on second request for uncacheable resource, got %s", resp2.Header.Get("X-Cache"))
	}
}

func TestCacheHitFlow(t *testing.T) {
	// Initialize local test cache
	cdnCache = cache.NewCache()
	nodeID = "test-edge"

	fetchCount := 0
	originMock := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fetchCount++
		w.Header().Set("Cache-Control", "public, max-age=3600")
		w.Header().Set("ETag", `"mock-etag"`)
		w.Header().Set("Content-Type", "text/plain")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("cacheable asset data"))
	}))
	defer originMock.Close()

	originURL = originMock.URL

	// 1st request -> Cache MISS
	rec1 := httptest.NewRecorder()
	req1 := httptest.NewRequest(http.MethodGet, "/static/asset.js", nil)
	handleProxy(rec1, req1)

	resp1 := rec1.Result()
	if resp1.Header.Get("X-Cache") != "MISS" {
		t.Errorf("expected X-Cache MISS, got %s", resp1.Header.Get("X-Cache"))
	}
	if fetchCount != 1 {
		t.Fatalf("expected origin fetch count 1, got %d", fetchCount)
	}

	// 2nd request -> Cache HIT
	rec2 := httptest.NewRecorder()
	req2 := httptest.NewRequest(http.MethodGet, "/static/asset.js", nil)
	handleProxy(rec2, req2)

	resp2 := rec2.Result()
	if resp2.Header.Get("X-Cache") != "HIT" {
		t.Errorf("expected X-Cache HIT, got %s", resp2.Header.Get("X-Cache"))
	}
	if fetchCount != 1 {
		t.Fatalf("expected origin fetch count to remain 1 on HIT, got %d", fetchCount)
	}
}

func TestQueryStringCacheIsolation(t *testing.T) {
	// Initialize local test cache
	cdnCache = cache.NewCache()
	nodeID = "test-edge"

	originMock := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "public, max-age=3600")
		w.Header().Set("Content-Type", "text/plain")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("content:" + r.URL.Path + "?" + r.URL.RawQuery))
	}))
	defer originMock.Close()

	originURL = originMock.URL

	// 1. Request /file?id=1 -> Expect MISS and content: /file?id=1
	rec1 := httptest.NewRecorder()
	req1 := httptest.NewRequest(http.MethodGet, "/file?id=1", nil)
	handleProxy(rec1, req1)

	resp1 := rec1.Result()
	if resp1.Header.Get("X-Cache") != "MISS" {
		t.Errorf("expected X-Cache MISS for /file?id=1, got %s", resp1.Header.Get("X-Cache"))
	}
	if body := rec1.Body.String(); body != "content:/file?id=1" {
		t.Errorf("expected body 'content:/file?id=1', got %q", body)
	}

	// 2. Request /file?id=2 -> Must be a MISS (not shared with id=1) and content: /file?id=2
	rec2 := httptest.NewRecorder()
	req2 := httptest.NewRequest(http.MethodGet, "/file?id=2", nil)
	handleProxy(rec2, req2)

	resp2 := rec2.Result()
	if resp2.Header.Get("X-Cache") != "MISS" {
		t.Errorf("expected X-Cache MISS for /file?id=2, got %s", resp2.Header.Get("X-Cache"))
	}
	if body := rec2.Body.String(); body != "content:/file?id=2" {
		t.Errorf("expected body 'content:/file?id=2', got %q", body)
	}

	// 3. Request /file?id=1 again -> Must be a HIT with original id=1 content
	rec3 := httptest.NewRecorder()
	req3 := httptest.NewRequest(http.MethodGet, "/file?id=1", nil)
	handleProxy(rec3, req3)

	resp3 := rec3.Result()
	if resp3.Header.Get("X-Cache") != "HIT" {
		t.Errorf("expected X-Cache HIT for /file?id=1, got %s", resp3.Header.Get("X-Cache"))
	}
	if body := rec3.Body.String(); body != "content:/file?id=1" {
		t.Errorf("expected cached body 'content:/file?id=1', got %q", body)
	}

	// 4. Request /file?id=2 again -> Must be a HIT with original id=2 content
	rec4 := httptest.NewRecorder()
	req4 := httptest.NewRequest(http.MethodGet, "/file?id=2", nil)
	handleProxy(rec4, req4)

	resp4 := rec4.Result()
	if resp4.Header.Get("X-Cache") != "HIT" {
		t.Errorf("expected X-Cache HIT for /file?id=2, got %s", resp4.Header.Get("X-Cache"))
	}
	if body := rec4.Body.String(); body != "content:/file?id=2" {
		t.Errorf("expected cached body 'content:/file?id=2', got %q", body)
	}

	// 5. Request path-only /file -> Must be a separate MISS
	rec5 := httptest.NewRecorder()
	req5 := httptest.NewRequest(http.MethodGet, "/file", nil)
	handleProxy(rec5, req5)

	resp5 := rec5.Result()
	if resp5.Header.Get("X-Cache") != "MISS" {
		t.Errorf("expected X-Cache MISS for path-only /file, got %s", resp5.Header.Get("X-Cache"))
	}
	if body := rec5.Body.String(); body != "content:/file?" {
		t.Errorf("expected body 'content:/file?', got %q", body)
	}
}
