package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"mini-cdn/pkg/cache"
)

func TestConcurrentColdBurst(t *testing.T) {
	for _, enabled := range []bool{false, true} {
		name := "baseline"
		if enabled {
			name = "coalescing"
		}
		t.Run(name, func(t *testing.T) {
			oldURL, oldCache, oldEnabled := originURL, cdnCache, coalescingEnabled
			defer func() { originURL, cdnCache, coalescingEnabled = oldURL, oldCache, oldEnabled }()
			cdnCache = cache.NewCache()
			coalescingEnabled = enabled
			const clients = 32
			var fetches int32
			releaseOrigin := make(chan struct{})
			var unblock sync.Once
			origin := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				atomic.AddInt32(&fetches, 1)
				<-releaseOrigin
				w.Header().Set("Cache-Control", "public, max-age=60")
				w.Write([]byte("shared asset"))
			}))
			defer origin.Close()
			defer unblock.Do(func() { close(releaseOrigin) })
			originURL = origin.URL
			var wg sync.WaitGroup
			responses := make([]*httptest.ResponseRecorder, clients)
			for i := range responses {
				responses[i] = httptest.NewRecorder()
				wg.Add(1)
				go func(i int) {
					defer wg.Done()
					handleProxy(responses[i], httptest.NewRequest("GET", "/burst", nil))
				}(i)
			}
			deadline := time.Now().Add(5 * time.Second)
			for {
				ready := atomic.LoadInt32(&fetches) == clients
				if enabled {
					cacheFills.mu.Lock()
					c := cacheFills.calls["/burst"]
					ready = c != nil && c.refs == clients && atomic.LoadInt32(&fetches) == 1
					cacheFills.mu.Unlock()
				}
				if ready {
					break
				}
				if time.Now().After(deadline) {
					unblock.Do(func() { close(releaseOrigin) })
					wg.Wait()
					t.Fatal("burst did not reach the origin/gate barrier")
				}
				runtime.Gosched()
			}
			unblock.Do(func() { close(releaseOrigin) })
			wg.Wait()
			want := int32(clients)
			if enabled {
				want = 1
			}
			if got := atomic.LoadInt32(&fetches); got != want {
				t.Fatalf("origin attempts = %d, want %d", got, want)
			}
			for _, rec := range responses {
				if rec.Code != 200 || rec.Body.String() != "shared asset" {
					t.Fatalf("invalid response: %d %q", rec.Code, rec.Body.String())
				}
			}
			hits, misses, _ := cdnCache.Stats()
			if hits != 0 || misses != clients {
				t.Fatalf("initial lookup stats = %d/%d", hits, misses)
			}
		})
	}
}

func TestFillGateCancellationAndKeyIsolation(t *testing.T) {
	var group fillGroup
	release, err := group.acquire(context.Background(), "a")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := group.acquire(ctx, "a"); err != context.Canceled {
		t.Fatalf("got %v", err)
	}
	other, err := group.acquire(context.Background(), "b")
	if err != nil {
		t.Fatal(err)
	}
	other()
	release()
	if len(group.calls) != 0 {
		t.Fatal("finished gates leaked")
	}
}

func TestUnsafeResponsesAreNotCached(t *testing.T) {
	for _, header := range []string{"Vary", "Set-Cookie"} {
		t.Run(header, func(t *testing.T) {
			oldURL, oldCache := originURL, cdnCache
			defer func() { originURL, cdnCache = oldURL, oldCache }()
			cdnCache = cache.NewCache()
			origin := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Cache-Control", "public, max-age=60")
				w.Header().Set(header, "example")
				w.Write([]byte("variant"))
			}))
			defer origin.Close()
			originURL = origin.URL
			handleProxy(httptest.NewRecorder(), httptest.NewRequest("GET", "/variant", nil))
			if _, ok := cdnCache.Peek("/variant"); ok {
				t.Fatal("unsafe response was cached")
			}
		})
	}
}
