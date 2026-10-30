CC      ?= gcc
CFLAGS ?= -Wall -Wextra -O2

all: sudoku_validator

sudoku_validator: sudoku_validator.c
	$(CC) $(CFLAGS) -pthread $< -o $@

sudoku_validator_tsan: sudoku_validator.c
	$(CC) -g -O1 -fsanitize=thread -pthread $< -o $@

sudoku_validator_asan: sudoku_validator.c
	$(CC) -g -O1 -fsanitize=address,undefined -pthread $< -o $@

sanitizers: sudoku_validator_tsan sudoku_validator_asan

test: all sanitizers
	REQUIRE_SANITIZERS=1 ./run_tests.sh

clean:
	rm -f sudoku_validator sudoku_validator_tsan sudoku_validator_asan

.PHONY: all sanitizers test clean
