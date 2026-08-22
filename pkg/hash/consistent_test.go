package hash

import (
	"testing"
)

func TestRing_EmptyRing(t *testing.T) {
	ring := NewRing(50)

	node, err := ring.GetNode("/assets/logo.png")
	if err == nil {
		t.Fatalf("expected error from empty ring, got node: %q", node)
	}
	if node != "" {
		t.Errorf("expected empty node string, got %q", node)
	}

	candidates := ring.GetCandidates("/assets/logo.png")
	if len(candidates) != 0 {
		t.Errorf("expected 0 candidates from empty ring, got %d", len(candidates))
	}
}

func TestRing_DeterministicNodeSelection(t *testing.T) {
	ring := NewRing(50)
	nodes := []string{"edge-1", "edge-2", "edge-3"}
	for _, n := range nodes {
		ring.AddNode(n)
	}

	key := "/assets/logo.png"

	firstNode, err := ring.GetNode(key)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if firstNode == "" {
		t.Fatalf("expected non-empty node name")
	}

	// Repeated lookups must return the exact same node
	for i := 0; i < 50; i++ {
		n, err := ring.GetNode(key)
		if err != nil {
			t.Fatalf("unexpected error on iteration %d: %v", i, err)
		}
		if n != firstNode {
			t.Fatalf("expected deterministic selection %s, got %s on iteration %d", firstNode, n, i)
		}
	}
}

func TestRing_Candidates(t *testing.T) {
	ring := NewRing(50)
	expectedNodes := []string{"edge-1", "edge-2", "edge-3"}
	for _, n := range expectedNodes {
		ring.AddNode(n)
	}

	key := "/assets/app.js"
	candidates := ring.GetCandidates(key)

	if len(candidates) != len(expectedNodes) {
		t.Fatalf("expected %d candidates, got %d", len(expectedNodes), len(candidates))
	}

	// Check that all unique nodes are included
	seen := make(map[string]bool)
	for _, c := range candidates {
		if seen[c] {
			t.Errorf("duplicate candidate %s found in candidates list", c)
		}
		seen[c] = true
	}

	for _, n := range expectedNodes {
		if !seen[n] {
			t.Errorf("expected node %s to be in candidate list", n)
		}
	}

	// Verify primary candidate matches GetNode result
	primary, err := ring.GetNode(key)
	if err != nil {
		t.Fatalf("unexpected error from GetNode: %v", err)
	}
	if candidates[0] != primary {
		t.Errorf("expected first candidate %s to match GetNode %s", candidates[0], primary)
	}
}

func TestRing_SetNodes(t *testing.T) {
	ring := NewRing(50)

	// Set initial nodes
	ring.SetNodes([]string{"edge-1", "edge-2"})

	candidates := ring.GetCandidates("/test")
	if len(candidates) != 2 {
		t.Fatalf("expected 2 candidates, got %d", len(candidates))
	}

	// Re-set nodes to only edge-3
	ring.SetNodes([]string{"edge-3"})

	node, err := ring.GetNode("/test")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if node != "edge-3" {
		t.Fatalf("expected node edge-3, got %s", node)
	}

	candidates = ring.GetCandidates("/test")
	if len(candidates) != 1 || candidates[0] != "edge-3" {
		t.Fatalf("expected [edge-3], got %v", candidates)
	}
}

func TestRing_AddAndRemoveNode(t *testing.T) {
	ring := NewRing(50)

	ring.AddNode("edge-1")
	ring.AddNode("edge-2")

	// Idempotent add
	ring.AddNode("edge-1")

	candidates := ring.GetCandidates("/test")
	if len(candidates) != 2 {
		t.Fatalf("expected 2 candidates, got %d", len(candidates))
	}

	ring.RemoveNode("edge-1")

	candidates = ring.GetCandidates("/test")
	if len(candidates) != 1 || candidates[0] != "edge-2" {
		t.Fatalf("expected [edge-2] after removing edge-1, got %v", candidates)
	}

	node, err := ring.GetNode("/test")
	if err != nil || node != "edge-2" {
		t.Fatalf("expected edge-2, got %s, err: %v", node, err)
	}
}
