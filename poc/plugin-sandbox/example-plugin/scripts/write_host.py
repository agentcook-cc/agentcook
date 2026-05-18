try:
    with open("/etc/hacked", "w") as f:
        f.write("pwned")
    print("FAIL: was able to write!")
except Exception as e:
    print(f"BLOCKED: {e}")
