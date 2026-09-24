CC = cc
CFLAGS = -std=c11 -O2 -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror

.PHONY: all clean test
all: parent child

parent: parent.c common.h
	$(CC) $(CFLAGS) parent.c -o parent

child: child.c common.h
	$(CC) $(CFLAGS) child.c -o child

test: all
	python3 tests/test_lab.py

clean:
	rm -f parent child parent.exe child.exe
