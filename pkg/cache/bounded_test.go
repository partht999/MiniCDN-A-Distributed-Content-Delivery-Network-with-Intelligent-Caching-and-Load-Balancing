package cache

import (
	"net/http"
	"testing"
	"time"
)

func TestByteBoundAndLRU(t *testing.T) {
	c := NewBoundedCache(8)
	c.Set("a", 200, []byte("1234"), nil, time.Minute)
	c.Set("b", 200, []byte("5678"), nil, time.Minute)
	c.Get("a")
	c.Set("c", 200, []byte("abcd"), nil, time.Minute)
	if _, hit := c.Get("b"); hit {
		t.Fatal("least recent item survived")
	}
	if _, hit := c.Get("a"); !hit {
		t.Fatal("recent item evicted")
	}
	bytes, evictions := c.Usage()
	if bytes != 8 || evictions != 1 {
		t.Fatalf("usage %d evictions %d", bytes, evictions)
	}
	c.Set("large", 200, []byte("123456789"), nil, time.Minute)
	if _, hit := c.Get("large"); hit {
		t.Fatal("oversized object cached")
	}
	c.Set("a", 200, []byte("1"), nil, time.Minute)
	bytes, _ = c.Usage()
	if bytes != 5 {
		t.Fatalf("replacement accounting %d", bytes)
	}
	c.DeletePrefix("c")
	bytes, _ = c.Usage()
	if bytes != 1 {
		t.Fatal("prefix deletion accounting")
	}
	c.Clear()
	bytes, _ = c.Usage()
	if bytes != 0 {
		t.Fatal("clear accounting")
	}
}

func TestSetCopiesBodyAndHeaders(t *testing.T) {
	c := NewCache()
	body := []byte("hello")
	header := http.Header{"X-Test": []string{"before"}}
	c.Set("a", 200, body, header, time.Minute)
	body[0] = 'X'
	header.Set("X-Test", "after")
	entry, _ := c.Get("a")
	if string(entry.Body) != "hello" || entry.Header.Get("X-Test") != "before" {
		t.Fatal("caller mutated cache")
	}
}
