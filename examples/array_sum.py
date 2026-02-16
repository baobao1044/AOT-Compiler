def sum_array(n: int) -> int:
    a = [0] * n

    i = 0
    while i < n:
        a[i] = i
        i = i + 1

    total = 0
    j = 0
    while j < n:
        total = total + a[j]
        j = j + 1

    return total
