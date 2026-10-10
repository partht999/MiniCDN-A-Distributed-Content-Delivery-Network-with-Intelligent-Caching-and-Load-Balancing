package cache

import (
	"fmt"
	"net/http"
	"sync"
	"testing"
	"time"
)

func TestCache_Miss(t *testing.T) {
	c := NewCache()

	entry, hit := c.Get("/nonexistent")
	if hit {
		t.Fatalf("expected cache miss, got hit")
	}
	if entry != nil {
		t.Fatalf("expected nil entry on miss, got: %v", entry)
	}

	hits, misses, ratio := c.Stats()
	if hits != 0 || misses != 1 || ratio != 0.0 {
		t.Fatalf("expected 0 hits, 1 miss, 0.0 ratio; got hits=%d misses=%d ratio=%f", hits, misses, ratio)
	}
}

func TestCache_Hit(t *testing.T) {
	c := NewCache()

	header := make(http.Header)
	header.Set("Content-Type", "text/plain")
	header.Set("X-Custom", "test-val")

	body := []byte("hello mini cdn")
	key := "/test/asset"

	c.Set(key, http.StatusOK, body, header, 10*time.Second)

	entry, hit := c.Get(key)
	if !hit {
		t.Fatalf("expected cache hit, got miss")
	}
	if entry == nil {
		t.Fatalf("expected non-nil entry on hit")
	}
	if entry.StatusCode != http.StatusOK {
		t.Errorf("expected status code %d, got %d", http.StatusOK, entry.StatusCode)
	}
	if string(entry.Body) != string(body) {
		t.Errorf("expected body %q, got %q", string(body), string(entry.Body))
	}
	if entry.Header.Get("Content-Type") != "text/plain" {
		t.Errorf("expected Content-Type text/plain, got %q", entry.Header.Get("Content-Type"))
	}
	if entry.Header.Get("X-Custom") != "test-val" {
		t.Errorf("expected X-Custom test-val, got %q", entry.Header.Get("X-Custom"))
	}

	hits, misses, ratio := c.Stats()
	if hits != 1 || misses != 0 || ratio != 1.0 {
		t.Errorf("expected 1 hit, 0 misses, 1.0 ratio; got hits=%d misses=%d ratio=%f", hits, misses, ratio)
	}
}

func TestCache_TTLExpiration(t *testing.T) {
	c := NewCache()

	key := "/short-lived"
	c.Set(key, http.StatusOK, []byte("temporary"), nil, 25*time.Millisecond)

	// Immediate lookup should hit
	entry, hit := c.Get(key)
	if !hit || entry == nil {
		t.Fatalf("expected immediate hit for key before expiration")
	}

	// Wait for expiration
	time.Sleep(40 * time.Millisecond)

	// Subsequent lookup should miss and delete expired item
	entry, hit = c.Get(key)
	if hit {
		t.Fatalf("expected cache miss after TTL expiration, got hit")
	}
	if entry != nil {
		t.Fatalf("expected nil entry after expiration, got %v", entry)
	}

	// Retain bounded stale content only for conditional origin validation.
	c.mu.RLock()
	_, exists := c.items[key]
	c.mu.RUnlock()
	if !exists {
		t.Errorf("expected stale key %s to remain for revalidation", key)
	}
}

func TestCache_Delete(t *testing.T) {
	c := NewCache()

	key := "/purge-target"
	c.Set(key, http.StatusOK, []byte("data"), nil, 10*time.Second)

	_, hit := c.Get(key)
	if !hit {
		t.Fatalf("expected hit before deletion")
	}

	c.Delete(key)

	_, hit = c.Get(key)
	if hit {
		t.Fatalf("expected miss after deletion")
	}
}

func TestCache_Clear(t *testing.T) {
	c := NewCache()

	c.Set("/k1", http.StatusOK, []byte("v1"), nil, 10*time.Second)
	c.Set("/k2", http.StatusOK, []byte("v2"), nil, 10*time.Second)

	c.Clear()

	if _, hit := c.Get("/k1"); hit {
		t.Errorf("expected miss for /k1 after clear")
	}
	if _, hit := c.Get("/k2"); hit {
		t.Errorf("expected miss for /k2 after clear")
	}
}

func TestCache_Stats(t *testing.T) {
	c := NewCache()

	// Initial stats on empty cache
	h, m, r := c.Stats()
	if h != 0 || m != 0 || r != 0.0 {
		t.Fatalf("expected (0, 0, 0.0) initially, got (%d, %d, %f)", h, m, r)
	}

	c.Set("/k1", http.StatusOK, []byte("data"), nil, 10*time.Second)

	// 3 hits
	c.Get("/k1")
	c.Get("/k1")
	c.Get("/k1")

	// 1 miss
	c.Get("/missing")

	hits, misses, ratio := c.Stats()
	if hits != 3 || misses != 1 {
		t.Fatalf("expected 3 hits, 1 miss; got %d hits, %d misses", hits, misses)
	}
	expectedRatio := 3.0 / 4.0
	if ratio != expectedRatio {
		t.Fatalf("expected hit ratio %f, got %f", expectedRatio, ratio)
	}
}

func TestCache_ConcurrentAccess(t *testing.T) {
	c := NewCache()
	var wg sync.WaitGroup

	numGoroutines := 30
	numOperations := 100

	for g := 0; g < numGoroutines; g++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for i := 0; i < numOperations; i++ {
				key := fmt.Sprintf("/key-%d", (id+i)%10)

				switch i % 4 {
				case 0:
					c.Set(key, http.StatusOK, []byte(fmt.Sprintf("val-%d", i)), nil, 1*time.Second)
				case 1:
					c.Get(key)
				case 2:
					c.Delete(key)
				case 3:
					c.Stats()
				}
			}
		}(g)
	}

	wg.Wait()
}
