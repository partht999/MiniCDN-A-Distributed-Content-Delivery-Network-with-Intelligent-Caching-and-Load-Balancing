package main

import (
	"github.com/prometheus/client_golang/prometheus"
	"sort"
	"sync"
)

// selector reserves an in-flight slot before releasing its lock. The load signal
// covers this router's requests, not CPU load or requests sent directly to edges.
type selector struct {
	mu    sync.Mutex
	next  uint64
	loads map[string]int
}

var inflightDescription = prometheus.NewDesc("router_inflight_requests", "Requests currently reserved by this router per edge.", []string{"node_id"}, nil)

func (s *selector) Describe(ch chan<- *prometheus.Desc) { ch <- inflightDescription }
func (s *selector) Collect(ch chan<- prometheus.Metric) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for id, load := range s.loads {
		ch <- prometheus.MustNewConstMetric(inflightDescription, prometheus.GaugeValue, float64(load), id)
	}
}

func (s *selector) reserve(mode string, candidates []string, slack int) ([]string, func()) {
	s.mu.Lock()
	if s.loads == nil {
		s.loads = make(map[string]int)
	}
	ids := append([]string(nil), candidates...)
	if len(ids) == 0 {
		s.mu.Unlock()
		return nil, func() {}
	}
	if mode == "round_robin" {
		sort.Strings(ids)
		index := int(s.next % uint64(len(ids)))
		s.next++
		ids = append(ids[index:], ids[:index]...)
	} else if mode == "adaptive" {
		best := 0
		for i := range ids {
			if s.loads[ids[i]] < s.loads[ids[best]] {
				best = i
			}
		}
		// Preserve locality unless the owner exceeds the least-loaded edge by
		// the configured number of concurrent requests. This is a heuristic,
		// not the object-placement bound proved in the bounded-load papers.
		if s.loads[ids[0]] > s.loads[ids[best]]+slack {
			ids[0], ids[best] = ids[best], ids[0]
		}
	}
	owner := ids[0]
	s.loads[owner]++
	s.mu.Unlock()
	var once sync.Once
	return ids, func() { once.Do(func() { s.mu.Lock(); s.loads[owner]--; s.mu.Unlock() }) }
}

func (s *selector) load(id string) float64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	return float64(s.loads[id])
}
