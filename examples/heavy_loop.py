def heavy_loop(n: int) -> int:
    total = 0
    i = 0
    while i < n:
        total = total + i * 2
        i = i + 1
    return total
