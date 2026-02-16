from aotc import extern, native


@extern("m")
def sin(x: float) -> float:
    ...


@extern("m")
def cos(x: float) -> float:
    ...


@native
def trig_sum(x: float) -> float:
    return sin(x) + cos(x)


if __name__ == "__main__":
    print(trig_sum(1.0))
