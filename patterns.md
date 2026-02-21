# Python Coding Interview Patterns - Complete Reference

## 📚 Table of Contents
1. [Two Pointers](#1-two-pointers)
2. [Sliding Window](#2-sliding-window)
3. [Binary Search](#3-binary-search)
4. [Breadth-First Search (BFS)](#4-breadth-first-search-bfs)
5. [Depth-First Search (DFS)](#5-depth-first-search-dfs)
6. [Backtracking](#6-backtracking)
7. [Heaps (Priority Queue)](#7-heaps-priority-queue)
8. [Dynamic Programming](#8-dynamic-programming)

---

## 1. Two Pointers

### Core Concept
Use two pointers to traverse data structure, reducing time complexity from O(n²) to O(n).

### Template 1: Opposite Direction
```python
def two_pointers_opposite(arr):
    """Find pairs/triplets that meet certain criteria"""
    left, right = 0, len(arr) - 1
    result = []
    
    while left < right:
        current_sum = arr[left] + arr[right]
        
        if current_sum == target:
            result.append([arr[left], arr[right]])
            left += 1
            right -= 1
        elif current_sum < target:
            left += 1  # Need larger sum
        else:
            right -= 1  # Need smaller sum
    
    return result
```

### Template 2: Same Direction (Fast & Slow)
```python
def fast_slow_pointers(head):
    """Detect cycle in linked list"""
    slow = fast = head
    
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        
        if slow == fast:
            return True  # Cycle detected
    
    return False

def find_middle(head):
    """Find middle of linked list"""
    slow = fast = head
    
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
    
    return slow  # Middle node
```

### Common Problems
- Two Sum (sorted array)
- Three Sum
- Container with Most Water
- Remove Duplicates from Sorted Array
- Linked List Cycle

**Time:** O(n) | **Space:** O(1)

---

## 2. Sliding Window

### Core Concept
Maintain a window that expands/contracts based on conditions.

### Template 1: Fixed Window
```python
def fixed_window(arr, k):
    """Maximum sum of subarray of size k"""
    if len(arr) < k:
        return -1
    
    window_sum = sum(arr[:k])
    max_sum = window_sum
    
    for i in range(k, len(arr)):
        window_sum = window_sum - arr[i - k] + arr[i]
        max_sum = max(max_sum, window_sum)
    
    return max_sum
```

### Template 2: Variable Window
```python
def variable_window(s):
    """Longest substring without repeating characters"""
    char_set = set()
    left = max_length = 0
    
    for right in range(len(s)):
        # Shrink window until valid
        while s[right] in char_set:
            char_set.remove(s[left])
            left += 1
        
        char_set.add(s[right])
        max_length = max(max_length, right - left + 1)
    
    return max_length
```

### Template 3: Window with Counter
```python
from collections import Counter

def window_with_counter(s, t):
    """Minimum window substring containing all chars of t"""
    if not s or not t:
        return ""
    
    need = Counter(t)
    have = {}
    
    left = 0
    min_len = float('inf')
    result = ""
    formed = 0
    required = len(need)
    
    for right in range(len(s)):
        char = s[right]
        have[char] = have.get(char, 0) + 1
        
        if char in need and have[char] == need[char]:
            formed += 1
        
        # Try to shrink window
        while left <= right and formed == required:
            # Update result if smaller window
            if right - left + 1 < min_len:
                min_len = right - left + 1
                result = s[left:right + 1]
            
            char = s[left]
            have[char] -= 1
            if char in need and have[char] < need[char]:
                formed -= 1
            left += 1
    
    return result
```

### Common Problems
- Maximum Sum Subarray of Size K
- Longest Substring Without Repeating Characters
- Minimum Window Substring
- Longest Substring with K Distinct Characters

**Time:** O(n) | **Space:** O(k) where k is window size or charset

---

## 3. Binary Search

### Core Concept
Divide search space in half repeatedly. Works on sorted arrays or when you can define a condition that divides the search space.

### Template 1: Standard Binary Search
```python
def binary_search(arr, target):
    """Find target in sorted array"""
    left, right = 0, len(arr) - 1
    
    while left <= right:
        mid = left + (right - left) // 2
        
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    
    return -1  # Not found
```

### Template 2: Find First/Last Position
```python
def find_first_position(arr, target):
    """Find first occurrence of target"""
    left, right = 0, len(arr) - 1
    result = -1
    
    while left <= right:
        mid = left + (right - left) // 2
        
        if arr[mid] == target:
            result = mid
            right = mid - 1  # Continue searching left
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    
    return result

def find_last_position(arr, target):
    """Find last occurrence of target"""
    left, right = 0, len(arr) - 1
    result = -1
    
    while left <= right:
        mid = left + (right - left) // 2
        
        if arr[mid] == target:
            result = mid
            left = mid + 1  # Continue searching right
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    
    return result
```

### Template 3: Search in Rotated Array
```python
def search_rotated(arr, target):
    """Search in rotated sorted array"""
    left, right = 0, len(arr) - 1
    
    while left <= right:
        mid = left + (right - left) // 2
        
        if arr[mid] == target:
            return mid
        
        # Left half is sorted
        if arr[left] <= arr[mid]:
            if arr[left] <= target < arr[mid]:
                right = mid - 1
            else:
                left = mid + 1
        # Right half is sorted
        else:
            if arr[mid] < target <= arr[right]:
                left = mid + 1
            else:
                right = mid - 1
    
    return -1
```

### Common Problems
- Search Insert Position
- Find Peak Element
- Search in Rotated Sorted Array
- Find Minimum in Rotated Sorted Array
- Search a 2D Matrix

**Time:** O(log n) | **Space:** O(1)

---

## 4. Breadth-First Search (BFS)

### Core Concept
Explore nodes level by level using a queue.

### Template 1: Tree Level Order Traversal
```python
from collections import deque

def level_order_traversal(root):
    """Level order traversal of binary tree"""
    if not root:
        return []
    
    result = []
    queue = deque([root])
    
    while queue:
        level_size = len(queue)
        current_level = []
        
        for _ in range(level_size):
            node = queue.popleft()
            current_level.append(node.val)
            
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        
        result.append(current_level)
    
    return result
```

### Template 2: Graph BFS
```python
def bfs_graph(graph, start):
    """BFS traversal of graph"""
    visited = set([start])
    queue = deque([start])
    result = []
    
    while queue:
        node = queue.popleft()
        result.append(node)
        
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    
    return result
```

### Template 3: Shortest Path (Unweighted)
```python
def shortest_path(graph, start, end):
    """Find shortest path in unweighted graph"""
    if start == end:
        return 0
    
    visited = set([start])
    queue = deque([(start, 0)])
    
    while queue:
        node, distance = queue.popleft()
        
        for neighbor in graph[node]:
            if neighbor == end:
                return distance + 1
            
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))
    
    return -1  # No path found
```

### Template 4: Matrix BFS
```python
def matrix_bfs(matrix):
    """BFS on 2D matrix (e.g., 01 Matrix problem)"""
    if not matrix:
        return []
    
    rows, cols = len(matrix), len(matrix[0])
    queue = deque()
    visited = set()
    
    # Initialize queue with all starting points
    for i in range(rows):
        for j in range(cols):
            if matrix[i][j] == 0:
                queue.append((i, j, 0))
                visited.add((i, j))
    
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    result = [[0] * cols for _ in range(rows)]
    
    while queue:
        x, y, dist = queue.popleft()
        
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            
            if 0 <= nx < rows and 0 <= ny < cols and (nx, ny) not in visited:
                visited.add((nx, ny))
                result[nx][ny] = dist + 1
                queue.append((nx, ny, dist + 1))
    
    return result
```

### Common Problems
- Binary Tree Level Order Traversal
- Rotting Oranges
- Word Ladder
- Clone Graph
- 01 Matrix

**Time:** O(V + E) for graphs, O(n) for trees | **Space:** O(n)

---

## 5. Depth-First Search (DFS)

### Core Concept
Explore as deep as possible before backtracking.

### Template 1: Tree DFS (Recursive)
```python
def dfs_tree(root):
    """DFS traversal patterns for binary tree"""
    
    def preorder(node):
        if not node:
            return []
        return [node.val] + preorder(node.left) + preorder(node.right)
    
    def inorder(node):
        if not node:
            return []
        return inorder(node.left) + [node.val] + inorder(node.right)
    
    def postorder(node):
        if not node:
            return []
        return postorder(node.left) + postorder(node.right) + [node.val]
    
    return preorder(root)
```

### Template 2: Graph DFS
```python
def dfs_graph(graph, start):
    """DFS traversal of graph"""
    visited = set()
    result = []
    
    def dfs(node):
        visited.add(node)
        result.append(node)
        
        for neighbor in graph[node]:
            if neighbor not in visited:
                dfs(neighbor)
    
    dfs(start)
    return result
```

### Template 3: Matrix DFS (Number of Islands)
```python
def num_islands(grid):
    """Count number of islands in 2D grid"""
    if not grid:
        return 0
    
    rows, cols = len(grid), len(grid[0])
    islands = 0
    
    def dfs(i, j):
        if i < 0 or i >= rows or j < 0 or j >= cols or grid[i][j] == '0':
            return
        
        grid[i][j] = '0'  # Mark as visited
        
        # Explore all 4 directions
        dfs(i + 1, j)
        dfs(i - 1, j)
        dfs(i, j + 1)
        dfs(i, j - 1)
    
    for i in range(rows):
        for j in range(cols):
            if grid[i][j] == '1':
                dfs(i, j)
                islands += 1
    
    return islands
```

### Template 4: Path Sum in Tree
```python
def has_path_sum(root, target_sum):
    """Check if tree has root-to-leaf path with given sum"""
    if not root:
        return False
    
    if not root.left and not root.right:
        return root.val == target_sum
    
    remaining = target_sum - root.val
    return (has_path_sum(root.left, remaining) or 
            has_path_sum(root.right, remaining))
```

### Common Problems
- Number of Islands
- Max Area of Island
- Path Sum
- Binary Tree Maximum Path Sum
- Course Schedule (Cycle Detection)

**Time:** O(V + E) for graphs, O(n) for trees | **Space:** O(h) for recursion stack

---

## 6. Backtracking

### Core Concept
Build solution incrementally, abandon paths that fail to meet constraints.

### Template 1: Generate Combinations
```python
def combinations(n, k):
    """Generate all combinations of k numbers from 1 to n"""
    result = []
    
    def backtrack(start, path):
        if len(path) == k:
            result.append(path[:])  # Make a copy
            return
        
        for i in range(start, n + 1):
            path.append(i)
            backtrack(i + 1, path)
            path.pop()  # Backtrack
    
    backtrack(1, [])
    return result
```

### Template 2: Generate Permutations
```python
def permutations(nums):
    """Generate all permutations of array"""
    result = []
    
    def backtrack(path, remaining):
        if not remaining:
            result.append(path[:])
            return
        
        for i in range(len(remaining)):
            path.append(remaining[i])
            backtrack(path, remaining[:i] + remaining[i+1:])
            path.pop()
    
    backtrack([], nums)
    return result
```

### Template 3: Subset Generation
```python
def subsets(nums):
    """Generate all subsets (power set)"""
    result = []
    
    def backtrack(start, path):
        result.append(path[:])  # Add current subset
        
        for i in range(start, len(nums)):
            path.append(nums[i])
            backtrack(i + 1, path)
            path.pop()
    
    backtrack(0, [])
    return result
```

### Template 4: N-Queens
```python
def solve_n_queens(n):
    """Solve N-Queens problem"""
    result = []
    board = [['.' for _ in range(n)] for _ in range(n)]
    
    def is_valid(row, col):
        # Check column
        for i in range(row):
            if board[i][col] == 'Q':
                return False
        
        # Check diagonal (top-left)
        i, j = row - 1, col - 1
        while i >= 0 and j >= 0:
            if board[i][j] == 'Q':
                return False
            i -= 1
            j -= 1
        
        # Check diagonal (top-right)
        i, j = row - 1, col + 1
        while i >= 0 and j < n:
            if board[i][j] == 'Q':
                return False
            i -= 1
            j += 1
        
        return True
    
    def backtrack(row):
        if row == n:
            result.append([''.join(row) for row in board])
            return
        
        for col in range(n):
            if is_valid(row, col):
                board[row][col] = 'Q'
                backtrack(row + 1)
                board[row][col] = '.'  # Backtrack
    
    backtrack(0)
    return result
```

### Template 5: Word Search
```python
def word_search(board, word):
    """Find if word exists in 2D board"""
    if not board:
        return False
    
    rows, cols = len(board), len(board[0])
    
    def backtrack(i, j, index):
        if index == len(word):
            return True
        
        if (i < 0 or i >= rows or j < 0 or j >= cols or 
            board[i][j] != word[index]):
            return False
        
        # Mark as visited
        temp = board[i][j]
        board[i][j] = '#'
        
        # Explore all 4 directions
        found = (backtrack(i + 1, j, index + 1) or
                backtrack(i - 1, j, index + 1) or
                backtrack(i, j + 1, index + 1) or
                backtrack(i, j - 1, index + 1))
        
        # Backtrack
        board[i][j] = temp
        
        return found
    
    for i in range(rows):
        for j in range(cols):
            if backtrack(i, j, 0):
                return True
    
    return False
```

### Common Problems
- Letter Combinations of a Phone Number
- Generate Parentheses
- Combination Sum
- Palindrome Partitioning
- Sudoku Solver

**Time:** Often O(2^n) or O(n!) | **Space:** O(n) for recursion stack

---

## 7. Heaps (Priority Queue)

### Core Concept
Maintain a collection where you can efficiently access the min/max element.

### Template 1: Top K Elements
```python
import heapq

def top_k_frequent(nums, k):
    """Find k most frequent elements"""
    from collections import Counter
    
    count = Counter(nums)
    
    # Use min heap of size k
    heap = []
    for num, freq in count.items():
        heapq.heappush(heap, (freq, num))
        if len(heap) > k:
            heapq.heappop(heap)
    
    return [num for freq, num in heap]
```

### Template 2: K Closest Points
```python
def k_closest_points(points, k):
    """Find k closest points to origin"""
    heap = []
    
    for x, y in points:
        dist = -(x*x + y*y)  # Negative for max heap
        
        if len(heap) < k:
            heapq.heappush(heap, (dist, [x, y]))
        elif dist > heap[0][0]:
            heapq.heapreplace(heap, (dist, [x, y]))
    
    return [point for _, point in heap]
```

### Template 3: Merge K Sorted Lists
```python
def merge_k_lists(lists):
    """Merge k sorted linked lists"""
    heap = []
    
    # Initialize heap with first element from each list
    for i, lst in enumerate(lists):
        if lst:
            heapq.heappush(heap, (lst.val, i, lst))
    
    dummy = ListNode(0)
    current = dummy
    
    while heap:
        val, idx, node = heapq.heappop(heap)
        current.next = node
        current = current.next
        
        if node.next:
            heapq.heappush(heap, (node.next.val, idx, node.next))
    
    return dummy.next
```

### Template 4: Running Median
```python
class MedianFinder:
    """Find median from data stream"""
    
    def __init__(self):
        self.max_heap = []  # Lower half
        self.min_heap = []  # Upper half
    
    def addNum(self, num):
        # Add to max_heap first
        heapq.heappush(self.max_heap, -num)
        
        # Balance: move max of lower half to upper half
        heapq.heappush(self.min_heap, 
                      -heapq.heappop(self.max_heap))
        
        # Maintain size property
        if len(self.min_heap) > len(self.max_heap):
            heapq.heappush(self.max_heap, 
                          -heapq.heappop(self.min_heap))
    
    def findMedian(self):
        if len(self.max_heap) > len(self.min_heap):
            return -self.max_heap[0]
        return (-self.max_heap[0] + self.min_heap[0]) / 2.0
```

### Common Problems
- Kth Largest Element in Array
- Top K Frequent Elements
- Merge K Sorted Lists
- Find Median from Data Stream
- Task Scheduler

**Time:** O(n log k) for top K problems | **Space:** O(k)

---

## 8. Dynamic Programming

### Core Concept
Break down problems into overlapping subproblems, solve each once, and store results.

### Template 1: 1D DP - Bottom Up
```python
def climb_stairs(n):
    """Number of ways to climb stairs (can take 1 or 2 steps)"""
    if n <= 2:
        return n
    
    dp = [0] * (n + 1)
    dp[1], dp[2] = 1, 2
    
    for i in range(3, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    
    return dp[n]

def climb_stairs_optimized(n):
    """Space-optimized version"""
    if n <= 2:
        return n
    
    prev2, prev1 = 1, 2
    
    for i in range(3, n + 1):
        current = prev1 + prev2
        prev2, prev1 = prev1, current
    
    return prev1
```

### Template 2: 1D DP - Top Down (Memoization)
```python
def word_break(s, word_dict):
    """Check if string can be segmented into dictionary words"""
    word_set = set(word_dict)
    memo = {}
    
    def dp(start):
        if start == len(s):
            return True
        
        if start in memo:
            return memo[start]
        
        for end in range(start + 1, len(s) + 1):
            if s[start:end] in word_set and dp(end):
                memo[start] = True
                return True
        
        memo[start] = False
        return False
    
    return dp(0)
```

### Template 3: 2D DP - Grid Problems
```python
def unique_paths(m, n):
    """Number of unique paths in m×n grid"""
    dp = [[1] * n for _ in range(m)]
    
    for i in range(1, m):
        for j in range(1, n):
            dp[i][j] = dp[i-1][j] + dp[i][j-1]
    
    return dp[m-1][n-1]

def min_path_sum(grid):
    """Minimum path sum from top-left to bottom-right"""
    if not grid:
        return 0
    
    m, n = len(grid), len(grid[0])
    
    # Initialize first row and column
    for i in range(1, m):
        grid[i][0] += grid[i-1][0]
    for j in range(1, n):
        grid[0][j] += grid[0][j-1]
    
    # Fill the rest
    for i in range(1, m):
        for j in range(1, n):
            grid[i][j] += min(grid[i-1][j], grid[i][j-1])
    
    return grid[m-1][n-1]
```

### Template 4: String DP - LCS/Edit Distance
```python
def longest_common_subsequence(text1, text2):
    """Find length of longest common subsequence"""
    m, n = len(text1), len(text2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if text1[i-1] == text2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    return dp[m][n]

def edit_distance(word1, word2):
    """Minimum operations to convert word1 to word2"""
    m, n = len(word1), len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    # Initialize base cases
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i-1] == word2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j],    # Delete
                                  dp[i][j-1],      # Insert
                                  dp[i-1][j-1])    # Replace
    
    return dp[m][n]
```

### Template 5: Knapsack Problems
```python
def knapsack_01(weights, values, capacity):
    """0/1 Knapsack - each item can be taken once"""
    n = len(weights)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    
    for i in range(1, n + 1):
        for w in range(1, capacity + 1):
            if weights[i-1] <= w:
                dp[i][w] = max(dp[i-1][w],
                              values[i-1] + dp[i-1][w - weights[i-1]])
            else:
                dp[i][w] = dp[i-1][w]
    
    return dp[n][capacity]

def coin_change(coins, amount):
    """Minimum coins needed to make amount"""
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    
    for coin in coins:
        for x in range(coin, amount + 1):
            dp[x] = min(dp[x], dp[x - coin] + 1)
    
    return dp[amount] if dp[amount] != float('inf') else -1
```

### Common Problems
- House Robber
- Longest Increasing Subsequence
- Maximum Subarray (Kadane's Algorithm)
- Decode Ways
- Best Time to Buy and Sell Stock

**Time:** Usually O(n²) or O(n·m) | **Space:** O(n) or O(n·m), can often be optimized

---

## 🎯 Quick Pattern Selection Guide

| Scenario | Pattern to Use |
|----------|---------------|
| Find pairs/triplets in sorted array | Two Pointers |
| Find cycle in linked list | Two Pointers (Fast & Slow) |
| Subarray/substring with condition | Sliding Window |
| Search in sorted array | Binary Search |
| Find in rotated array | Modified Binary Search |
| Tree level-by-level | BFS |
| Shortest path (unweighted) | BFS |
| Explore all paths | DFS |
| Count islands/components | DFS |
| Generate all combinations | Backtracking |
| N-Queens, Sudoku | Backtracking |
| Top K elements | Heap |
| Merge sorted streams | Heap |
| Optimize with subproblems | Dynamic Programming |
| Multiple choices at each step | Dynamic Programming |

---

## 💡 Pro Tips

1. **Start Simple**: Always begin with brute force, then optimize
2. **Draw It Out**: Visualize the problem before coding
3. **Edge Cases**: Empty input, single element, duplicates, negative numbers
4. **Time/Space Trade-off**: Sometimes using extra space simplifies the solution
5. **Pattern Recognition**: Most problems are variations of these 8 patterns
6. **Practice Order**: Two Pointers → Sliding Window → Binary Search → BFS/DFS → Backtracking → Heap → DP

---

*Keep this document handy during practice and interviews. The templates are battle-tested and cover 90% of interview problems!*