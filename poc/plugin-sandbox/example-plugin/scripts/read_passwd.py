try:
    with open("/etc/passwd", "r") as f:
        print(f.read())
except Exception as e:
    print(f"BLOCKED: {e}")
