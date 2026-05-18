.PHONY: build test test-attack-vectors clean

build:
	docker build -t agentcook-plugin-sandbox .

test: build test-attack-vectors

test-attack-vectors: build
	python test_attack_vectors.py

clean:
	docker rmi agentcook-plugin-sandbox 2>/dev/null || true
