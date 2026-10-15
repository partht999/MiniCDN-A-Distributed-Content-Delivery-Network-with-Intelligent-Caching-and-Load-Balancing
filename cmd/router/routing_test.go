package main

import (
	"sync"
	"testing"
)

func TestRoundRobinFairness(t *testing.T) {
	var s selector
	counts := map[string]int{}
	for i := 0; i < 30; i++ {
		ids, release := s.reserve("round_robin", []string{"c", "a", "b"}, 2)
		counts[ids[0]]++
		release()
	}
	for _, id := range []string{"a", "b", "c"} {
		if counts[id] != 10 {
			t.Fatalf("counts: %v", counts)
		}
	}
}

func TestAdaptiveLocalityAndSpillover(t *testing.T) {
	var s selector
	var releases []func()
	for i := 0; i < 3; i++ {
		ids, release := s.reserve("adaptive", []string{"a", "b", "c"}, 2)
		if ids[0] != "a" {
			t.Fatal("owner spilled before threshold")
		}
		releases = append(releases, release)
	}
	ids, release := s.reserve("adaptive", []string{"a", "b", "c"}, 2)
	if ids[0] != "b" {
		t.Fatalf("hot owner not spilled: %v", ids)
	}
	release()
	for _, done := range releases {
		done()
		done()
	}
	if s.load("a") != 0 || s.load("b") != 0 {
		t.Fatal("reservation leaked")
	}
}

func TestSelectorConcurrent(t *testing.T) {
	var s selector
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); _, done := s.reserve("adaptive", []string{"a", "b"}, 2); done() }()
	}
	wg.Wait()
	if s.load("a") != 0 || s.load("b") != 0 {
		t.Fatal("reservation leaked")
	}
}
