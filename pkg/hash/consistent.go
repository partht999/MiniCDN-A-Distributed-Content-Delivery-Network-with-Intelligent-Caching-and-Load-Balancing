package hash

import (
	"fmt"
	"hash/crc32"
	"sort"
	"sync"
)

// Ring represents a consistent hash ring.
type Ring struct {
	mu       sync.RWMutex
	replicas int               // Number of virtual nodes per physical node
	ring     []uint32          // Sorted list of virtual node hashes
	hashMap  map[uint32]string // Mapping from virtual node hash to physical node name
	nodes    map[string]bool   // Set of physical nodes
}

// NewRing creates and returns a new consistent hash Ring.
func NewRing(replicas int) *Ring {
	return &Ring{
		replicas: replicas,
		hashMap:  make(map[uint32]string),
		nodes:    make(map[string]bool),
	}
}

// AddNode adds a physical node to the ring.
func (r *Ring) AddNode(node string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.nodes[node] {
		return
	}
	r.nodes[node] = true

	for i := 0; i < r.replicas; i++ {
		hash := crc32.ChecksumIEEE([]byte(fmt.Sprintf("%s#%d", node, i)))
		r.ring = append(r.ring, hash)
		r.hashMap[hash] = node
	}
	sort.Slice(r.ring, func(i, j int) bool { return r.ring[i] < r.ring[j] })
}

// RemoveNode removes a physical node from the ring.
func (r *Ring) RemoveNode(node string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if !r.nodes[node] {
		return
	}
	delete(r.nodes, node)

	// Rebuild ring and hashMap
	newRing := make([]uint32, 0, len(r.ring)-(r.replicas))
	for hash, val := range r.hashMap {
		if val == node {
			delete(r.hashMap, hash)
		} else {
			newRing = append(newRing, hash)
		}
	}
	sort.Slice(newRing, func(i, j int) bool { return newRing[i] < newRing[j] })
	r.ring = newRing
}

// GetNode returns the closest physical node to the hashed key.
func (r *Ring) GetNode(key string) (string, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if len(r.ring) == 0 {
		return "", fmt.Errorf("empty hash ring")
	}

	hash := crc32.ChecksumIEEE([]byte(key))
	idx := sort.Search(len(r.ring), func(i int) bool {
		return r.ring[i] >= hash
	})

	// Wrap around if hash is greater than all hashes in the ring
	if idx == len(r.ring) {
		idx = 0
	}

	return r.hashMap[r.ring[idx]], nil
}

// GetCandidates returns all unique physical nodes in the order they appear
// clockwise on the ring starting from the hash of the key.
func (r *Ring) GetCandidates(key string) []string {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if len(r.ring) == 0 {
		return nil
	}

	hash := crc32.ChecksumIEEE([]byte(key))
	idx := sort.Search(len(r.ring), func(i int) bool {
		return r.ring[i] >= hash
	})

	if idx == len(r.ring) {
		idx = 0
	}

	candidates := make([]string, 0, len(r.nodes))
	seen := make(map[string]bool)

	// Traverse the ring from the starting index
	for i := 0; i < len(r.ring); i++ {
		currentIdx := (idx + i) % len(r.ring)
		node := r.hashMap[r.ring[currentIdx]]
		if !seen[node] {
			seen[node] = true
			candidates = append(candidates, node)
		}
		if len(candidates) == len(r.nodes) {
			break
		}
	}

	return candidates
}

// SetNodes sets the active physical nodes on the ring, rebuilding it completely.
func (r *Ring) SetNodes(nodes []string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.ring = nil
	r.hashMap = make(map[uint32]string)
	r.nodes = make(map[string]bool)

	for _, node := range nodes {
		r.nodes[node] = true
		for i := 0; i < r.replicas; i++ {
			hash := crc32.ChecksumIEEE([]byte(fmt.Sprintf("%s#%d", node, i)))
			r.ring = append(r.ring, hash)
			r.hashMap[hash] = node
		}
	}
	sort.Slice(r.ring, func(i, j int) bool { return r.ring[i] < r.ring[j] })
}
