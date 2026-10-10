package cache

import (
	"container/list"
	"net/http"
	"strings"
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
	mu        sync.RWMutex
	items     map[string]*CacheEntry
	order     *list.List
	positions map[string]*list.Element
	maxBytes  int64
	usedBytes int64
	evictions uint64
	hits      uint64
	misses    uint64
}

// NewCache initializes and returns a new Cache.
func NewCache() *Cache {
	return NewBoundedCache(64 * 1024 * 1024)
}

// NewBoundedCache bounds response-body bytes; metadata is additional overhead.
func NewBoundedCache(maxBytes int64) *Cache {
	if maxBytes <= 0 {
		maxBytes = 64 * 1024 * 1024
	}
	return &Cache{
		items: make(map[string]*CacheEntry),
		order: list.New(), positions: make(map[string]*list.Element), maxBytes: maxBytes,
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
		c.misses++
		return nil, false
	}

	c.hits++
	c.order.MoveToFront(c.positions[key])
	return entry, true
}

// Set stores a response in the cache with a specified TTL.
func (c *Cache) Set(key string, statusCode int, body []byte, header http.Header, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.remove(key)
	if int64(len(body)) > c.maxBytes || ttl <= 0 {
		return
	}
	for c.usedBytes+int64(len(body)) > c.maxBytes || len(c.items) >= 10000 {
		c.remove(c.order.Back().Value.(string))
		c.evictions++
	}

	c.items[key] = &CacheEntry{
		StatusCode: statusCode,
		Body:       append([]byte(nil), body...),
		Header:     copyHeader(header),
		Expiration: time.Now().Add(ttl),
	}
	c.positions[key] = c.order.PushFront(key)
	c.usedBytes += int64(len(body))
}

// Stale provides an immutable candidate for conditional origin revalidation.
// It must never be served before the origin confirms freshness.
func (c *Cache) Stale(key string) (*CacheEntry, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	entry, ok := c.items[key]
	return entry, ok && entry.IsExpired()
}

func (c *Cache) remove(key string) {
	if entry, ok := c.items[key]; ok {
		c.usedBytes -= int64(len(entry.Body))
		delete(c.items, key)
		c.order.Remove(c.positions[key])
		delete(c.positions, key)
	}
}

func (c *Cache) Usage() (int64, uint64) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.usedBytes, c.evictions
}

// Peek checks freshness without recording another request in cache statistics.
func (c *Cache) Peek(key string) (*CacheEntry, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	entry, ok := c.items[key]
	return entry, ok && !entry.IsExpired()
}

// Delete removes an item from the cache.
func (c *Cache) Delete(key string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.remove(key)
}

func (c *Cache) DeletePrefix(prefix string) int {
	c.mu.Lock()
	defer c.mu.Unlock()
	count := 0
	for key := range c.items {
		if strings.HasPrefix(key, prefix) {
			c.remove(key)
			count++
		}
	}
	return count
}

// Clear flushes all items from the cache.
func (c *Cache) Clear() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items = make(map[string]*CacheEntry)
	c.positions = make(map[string]*list.Element)
	c.order.Init()
	c.usedBytes = 0
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
