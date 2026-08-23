package cache

import (
	"net/http"
	"sync"
	"time"
)

// CacheEntry represents a cached HTTP response.
type CacheEntry struct {
	StatusCode int
	Body       []byte
	Header     http.Header
	Expiration time.Time
}

// IsExpired checks if the cache entry has expired.
func (e *CacheEntry) IsExpired() bool {
	return time.Now().After(e.Expiration)
}

// Cache is a thread-safe in-memory cache.
type Cache struct {
	mu     sync.RWMutex
	items  map[string]*CacheEntry
	hits   uint64
	misses uint64
}

// NewCache initializes and returns a new Cache.
func NewCache() *Cache {
	return &Cache{
		items: make(map[string]*CacheEntry),
	}
}

// Get retrieves an item from the cache.
// It returns the entry and a boolean indicating if it was found and not expired.
func (c *Cache) Get(key string) (*CacheEntry, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	entry, found := c.items[key]
	if !found {
		c.misses++
		return nil, false
	}

	if entry.IsExpired() {
		delete(c.items, key)
		c.misses++
		return nil, false
	}

	c.hits++
	return entry, true
}

// Set stores a response in the cache with a specified TTL.
func (c *Cache) Set(key string, statusCode int, body []byte, header http.Header, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.items[key] = &CacheEntry{
		StatusCode: statusCode,
		Body:       body,
		Header:     copyHeader(header),
		Expiration: time.Now().Add(ttl),
	}
}

// Delete removes an item from the cache.
func (c *Cache) Delete(key string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.items, key)
}

// Clear flushes all items from the cache.
func (c *Cache) Clear() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items = make(map[string]*CacheEntry)
}

// Stats returns the hits, misses, and hit ratio.
func (c *Cache) Stats() (uint64, uint64, float64) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	total := c.hits + c.misses
	if total == 0 {
		return 0, 0, 0.0
	}
	return c.hits, c.misses, float64(c.hits) / float64(total)
}

// Size returns the number of items in the cache.
func (c *Cache) Size() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return len(c.items)
}

// copyHeader duplicates an http.Header map to avoid concurrent modification issues.
func copyHeader(src http.Header) http.Header {
	if src == nil {
		return nil
	}
	dst := make(http.Header, len(src))
	for k, vv := range src {
		vvCopy := make([]string, len(vv))
		copy(vvCopy, vv)
		dst[k] = vvCopy
	}
	return dst
}
