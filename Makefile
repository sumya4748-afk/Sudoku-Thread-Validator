CC      ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -O2

all: sudoku_validator

sudoku_validator: sudoku_validator.c
	$(CC) $(CFLAGS) -pthread $< -o $@

sudoku_validator_tsan: sudoku_validator.c
	$(CC) -g -O1 -fsanitize=thread -pthread $< -o $@

sudoku_validator_asan: sudoku_validator.c
	$(CC) -g -O1 -fsanitize=address,undefined -pthread $< -o $@

tsan: sudoku_validator_tsan

asan: sudoku_validator_asan

sanitizers: sudoku_validator_tsan sudoku_validator_asan

test: all sanitizers
	REQUIRE_SANITIZERS=1 bash ./run_tests.sh

clean:
	rm -f sudoku_validator sudoku_validator_tsan sudoku_validator_asan

.PHONY: all tsan asan sanitizers test clean
