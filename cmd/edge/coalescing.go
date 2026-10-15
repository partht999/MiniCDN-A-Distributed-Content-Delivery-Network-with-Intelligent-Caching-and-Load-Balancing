package main

import (
	"context"
	"sync"
)

// fillGroup serializes cache fills for each key, without blocking other keys.
// Callers recheck the cache after acquiring the gate; uncacheable responses
// are fetched independently rather than shared between clients.
type fillGroup struct {
	mu    sync.Mutex
	calls map[string]*fillGate
}

type fillGate struct {
	token chan struct{}
	refs  int
}

func (g *fillGroup) acquire(ctx context.Context, key string) (func(), error) {
	g.mu.Lock()
	if g.calls == nil {
		g.calls = make(map[string]*fillGate)
	}
	c := g.calls[key]
	if c == nil {
		c = &fillGate{token: make(chan struct{}, 1)}
		c.token <- struct{}{}
		g.calls[key] = c
	}
	c.refs++
	g.mu.Unlock()

	drop := func() {
		g.mu.Lock()
		c.refs--
		if c.refs == 0 {
			delete(g.calls, key)
		}
		g.mu.Unlock()
	}
	select {
	case <-ctx.Done():
		drop()
		return nil, ctx.Err()
	case <-c.token:
		var once sync.Once
		return func() { once.Do(func() { c.token <- struct{}{}; drop() }) }, nil
	}
}
