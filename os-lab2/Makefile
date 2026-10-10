CC = gcc
CFLAGS = -std=c11 -O2 -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror

merge: merge.c
	$(CC) $(CFLAGS) -pthread $< -o $@

test: merge
	python3 tests/test.py

clean:
	rm -f merge

.PHONY: test clean
