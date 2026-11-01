#!/usr/bin/env bash
# Sudoku Validator — автомат тест
#   1) Файлын тест: хүлээгдэж буй гаралтын код (0 зөв / 1 буруу / 2 алдаа) x 3 горим
#   2) Бүсийн тусгаарлалт: аль worker-ууд 0 буцаахыг шалгах
#   3) Стресс: санамсаргүй ЗӨВ ба алдаатай судоку x 3 горим
#   4) ThreadSanitizer (data race), AddressSanitizer+UBSan (санах ой)
set -u
cd "$(dirname "$0")"
BIN=./sudoku_validator
PASS=0; FAIL=0; SKIP=0
STRESS=${STRESS:-300}

ok()   { PASS=$((PASS+1)); }
bad()  { FAIL=$((FAIL+1)); echo "  FAIL: $*"; }

expect_code() { # expect_code <хүлээгдэх код> <тайлбар> <аргументууд...>
  local want=$1 desc=$2; shift 2
  "$BIN" -q "$@" >/dev/null 2>&1; local got=$?
  if [ "$got" -eq "$want" ]; then ok; else bad "$desc: хүлээгдэж $want, гарсан $got ($*)"; fi
}

echo "== 1. Файлын тестүүд (горим бүрээр) =="
for mode in 1 11 27; do
  expect_code 0 "Figure 4.26"          -t $mode -f tests/valid_fig426.txt
  expect_code 0 "нэг мөрт формат"       -t $mode -f tests/valid_compact.txt
  expect_code 0 "анхдагч оролт"         -t $mode
  expect_code 1 "нэг нүд буруу"         -t $mode -f tests/invalid_one_cell.txt
  expect_code 1 "зөвхөн дэд тор буруу"  -t $mode -f tests/invalid_subgrids_only.txt
  expect_code 1 "зөвхөн багана буруу"   -t $mode -f tests/invalid_columns_only.txt
  expect_code 1 "бүрэн бус"             -t $mode -f tests/invalid_incomplete.txt
  expect_code 1 "бүгд 5"                -t $mode -f tests/invalid_all_same.txt
  expect_code 2 "80 нүд"                -t $mode -f tests/bad_short.txt
  expect_code 2 "үсэг"                  -t $mode -f tests/bad_char.txt
  expect_code 2 "файл байхгүй"          -t $mode -f tests/no_such_file.txt
  expect_code 1 "-s 5,5,0"              -t $mode -s 5,5,0
  expect_code 0 "stdin"                 -t $mode -f - < tests/valid_compact.txt
  expect_code 0 "UTF-8 BOM"             -t $mode -f tests/valid_bom.txt
done
# Benchmark must preserve Sudoku validity in its process exit status.
expect_code 0 "benchmark зөв судоку" -b 1 -f tests/valid_fig426.txt
expect_code 1 "benchmark буруу судоку" -b 1 -f tests/invalid_one_cell.txt
expect_code 2 "буруу горим -t 5" -t 5
expect_code 2 "-s trailing garbage" -s 1,1,6junk
expect_code 2 "-s overflow" -s 999999999999999999999,1,6
expect_code 2 "-s negative" -s -1,1,6
expect_code 2 "-s extra comma" -s 1,1,6,
expect_code 2 "-s missing value" -s 1,1,
expect_code 2 "-s second-field overflow" -s 1,999999999999999999999,6
expect_code 2 "буруу -s"         -s 10,1,1
expect_code 2 "-e abc"           -e abc
expect_code 2 "-e сөрөг"         -e -3
expect_code 2 "-e 82"            -e 82
expect_code 2 "-g abc"           -g abc
expect_code 2 "-g сөрөг"         -g -5
expect_code 2 "-t 11x"           -t 11x
expect_code 2 "-b abc"           -b abc
expect_code 2 "-b 0"             -b 0
expect_code 2 "-f ба -g хамт"    -f tests/valid_fig426.txt -g 7
expect_code 2 "-f хоёр удаа"     -f tests/valid_fig426.txt -f tests/invalid_one_cell.txt
expect_code 2 "хавтас оролт"     -f tests
expect_code 2 "мөрийн бүтэц буруу" -f tests/bad_shape.txt
expect_code 2 "илүү аргумент"    foo
echo "  дууслаа"

echo "== 2. Бүсийн тусгаарлалт (27 горим, valid[] массив) =="
# valid[] = 9 мөр | 9 багана | 9 дэд тор
check_valid_array() { # <файл> <хүлээгдэх valid[] мөр> <тайлбар>
  local got
  got=$("$BIN" -t 27 -f "$1" | sed -n 's/.*valid\[\] = \[\(.*\)\].*/\1/p')
  if [ "$got" = "$2" ]; then ok; else bad "$3: хүлээгдэж [$2], гарсан [$got]"; fi
}
check_valid_array tests/valid_fig426.txt \
  "1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1" "бүгд зөв"
check_valid_array tests/invalid_one_cell.txt \
  "0 1 1 1 1 1 1 1 1 0 1 1 1 1 1 1 1 1 0 1 1 1 1 1 1 1 1" "[1,1]: мөр1, багана1, тор1"
check_valid_array tests/invalid_subgrids_only.txt \
  "1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 0 0 0 0 0 0 0" "Латин квадрат: зөвхөн торууд"
check_valid_array tests/invalid_columns_only.txt \
  "1 1 1 1 1 1 1 1 1 0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1" "зөвхөн багана 1,2"
got=$("$BIN" -t 11 -f tests/invalid_subgrids_only.txt | sed -n 's/.*valid\[\] = \[\(.*\)\].*/\1/p')
[ "$got" = "1 1 0 0 0 0 0 0 0 0 0" ] && ok || bad "11 горим Латин квадрат: [$got]"
echo "  дууслаа"

echo "== 3. Стресс: $STRESS санамсаргүй судоку x 3 горим x (зөв + алдаатай) =="
for ((s=1; s<=STRESS; s++)); do
  e=$(( (s % 5) + 1 ))
  for mode in 1 11 27; do
    "$BIN" -q -t $mode -g $s >/dev/null;       [ $? -eq 0 ] && ok || bad "-g $s -t $mode зөв байх ёстой"
    "$BIN" -q -t $mode -g $s -e $e >/dev/null; [ $? -eq 1 ] && ok || bad "-g $s -e $e -t $mode буруу байх ёстой"
  done
done
echo "  дууслаа"

for SAN in tsan asan; do
  SB=./sudoku_validator_$SAN
  if [ -x "$SB" ]; then
    echo "== 4. $SAN: 50 судоку x 3 горим =="
    for ((s=1; s<=50; s++)); do
      for mode in 1 11 27; do
        out=$("$SB" -q -t $mode -g $s -e $((s % 3)) 2>&1)
        rc=$?
        expected=0
        [ $((s % 3)) -eq 0 ] || expected=1
        if [ "$rc" -ne "$expected" ] || echo "$out" | grep -qE "WARNING: ThreadSanitizer|ERROR: AddressSanitizer|runtime error|LeakSanitizer"; then
          bad "$SAN -g $s -t $mode: exit $rc, expected $expected"; echo "$out" | head -20
        else ok; fi
      done
    done
    echo "  дууслаа"
  else
    echo "== 4. $SAN: АЛГАСАВ ($SB олдсонгүй; 'make sanitizers' ажиллуулна уу) =="
    SKIP=$((SKIP+1))
  fi
done

echo
echo "НИЙТ: $PASS амжилттай, $FAIL амжилтгүй, $SKIP sanitizer хэсэг алгассан"
# REQUIRE_SANITIZERS=1 үед sanitizer хэсэг алгассан бол бүтэлгүйтсэнд тооцно
[ "$FAIL" -eq 0 ] && { [ "${REQUIRE_SANITIZERS:-0}" -eq 0 ] || [ "$SKIP" -eq 0 ]; }
