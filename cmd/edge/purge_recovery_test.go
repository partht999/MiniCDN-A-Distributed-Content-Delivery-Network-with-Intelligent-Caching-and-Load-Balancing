package main

import (
	"mini-cdn/pkg/cache"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestMissedPurgeGenerationFlushesUnlistedKeys(t *testing.T) {
	oldCache, oldGeneration := cdnCache, purgeGeneration
	defer func() { cdnCache, purgeGeneration = oldCache, oldGeneration }()
	cdnCache = cache.NewCache()
	purgeGeneration = 1
	cdnCache.Set("/missed-invalidation", 200, []byte("old"), nil, time.Hour)
	cdnCache.Set("/new-target", 200, []byte("old"), nil, time.Hour)
	rec := httptest.NewRecorder()
	handlePurge(rec, httptest.NewRequest("POST", "/internal/purge", strings.NewReader(`{"urls":["/new-target"],"generation":3}`)))
	if rec.Code != 200 || cdnCache.Size() != 0 || purgeGeneration != 3 {
		t.Fatal("skipped generation did not flush all content")
	}
	handlePurge(httptest.NewRecorder(), httptest.NewRequest("POST", "/internal/purge", strings.NewReader(`{"urls":["/new-target"],"generation":2}`)))
	if purgeGeneration != 3 {
		t.Fatal("out-of-order message moved generation backwards")
	}
}
