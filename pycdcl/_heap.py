"""Indexed binary max-heap of variables ordered by activity (VSIDS)."""

from __future__ import annotations


class VarHeap:
    """Max-heap over variable indices keyed by an external activity list.

    ``index[v]`` is the position of ``v`` in the heap, or -1 when absent, so
    membership checks, insertion and priority increases are all O(log n).
    """

    __slots__ = ("act", "heap", "index")

    def __init__(self, activity: list[float]) -> None:
        self.act = activity
        self.heap: list[int] = []
        self.index: list[int] = []

    def __len__(self) -> int:
        return len(self.heap)

    def __contains__(self, v: int) -> bool:
        return v < len(self.index) and self.index[v] >= 0

    def grow(self, n: int) -> None:
        while len(self.index) < n:
            self.index.append(-1)

    def insert(self, v: int) -> None:
        if self.index[v] >= 0:
            return
        self.index[v] = len(self.heap)
        self.heap.append(v)
        self._up(len(self.heap) - 1)

    def increased(self, v: int) -> None:
        """Restore the heap property after ``act[v]`` went up."""
        i = self.index[v]
        if i >= 0:
            self._up(i)

    def pop(self) -> int:
        heap, index = self.heap, self.index
        top = heap[0]
        last = heap.pop()
        index[top] = -1
        if heap:
            heap[0] = last
            index[last] = 0
            self._down(0)
        return top

    def rebuild(self, vs) -> None:
        for v in self.heap:
            self.index[v] = -1
        self.heap = []
        for v in vs:
            self.insert(v)

    def _up(self, i: int) -> None:
        heap, index, act = self.heap, self.index, self.act
        v = heap[i]
        a = act[v]
        while i > 0:
            parent = (i - 1) >> 1
            p = heap[parent]
            if act[p] >= a:
                break
            heap[i] = p
            index[p] = i
            i = parent
        heap[i] = v
        index[v] = i

    def _down(self, i: int) -> None:
        heap, index, act = self.heap, self.index, self.act
        n = len(heap)
        v = heap[i]
        a = act[v]
        while True:
            child = 2 * i + 1
            if child >= n:
                break
            if child + 1 < n and act[heap[child + 1]] > act[heap[child]]:
                child += 1
            c = heap[child]
            if act[c] <= a:
                break
            heap[i] = c
            index[c] = i
            i = child
        heap[i] = v
        index[v] = i
