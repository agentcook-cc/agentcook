data = []
try:
    while True:
        data.append(b"x" * (1024 * 1024 * 100))  # 100MB chunks
except MemoryError:
    print("BLOCKED: MemoryError")
