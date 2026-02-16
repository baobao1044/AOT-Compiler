from aotc import native, parallel_for


@native(parallel=True)
def tile_work(y_start: int, y_end: int, iterations: int) -> int:
    count = 0
    y = y_start
    while y < y_end:
        x = -20
        while x < 10:
            zr = 0.0
            zi = 0.0
            i = 0
            while i < iterations:
                zr2 = zr * zr - zi * zi
                zi = 2.0 * zr * zi
                zr = zr2
                i = i + 1
            count = count + 1
            x = x + 1
        y = y + 1
    return count


def run_parallel(threads: int = 4) -> int:
    parts = parallel_for(-15, 15, lambda s, e: tile_work(s, e, 40), threads=threads)
    return sum(parts)


if __name__ == "__main__":
    print(run_parallel(threads=4))
