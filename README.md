# Sudoku Solution Validator (Pthreads)

9×9 судокугийн шийдэл зөв эсэхийг олон worker thread-ээр зэрэгцээ шалгана.

## Бүтэц

| Файл | Агуулга |
|---|---|
| `sudoku_validator.c` | Үндсэн программ (C11 + Pthreads) |
| `Makefile` | `make`, `make tsan`, `make asan`, `make test` |
| `run_tests.sh` | Автомат тест (тохиолдлын тоо хувилбар/орчноос хамаарна) |
| `tests/*.txt` | Зөв, буруу, алдаатай оролтын жишээнүүд |
| `ui/sudoku_threads.html` | Интерактив дүрслэл (хөтөч дээр нээнэ) |

## Хөрвүүлэх, ажиллуулах

```sh
make                                   # sudoku_validator үүснэ
./sudoku_validator                     # Figure 4.26-ийн жишээг 11 thread-ээр шалгана
./sudoku_validator -f tests/invalid_one_cell.txt -t 27
./sudoku_validator -g 42 -e 2 -v       # seed 42 судоку, 2 алдаа, thread бүрийн мөрийг хэвлэнэ
echo "534678912672195348..." | ./sudoku_validator -f -
./sudoku_validator -b 2000             # 1 / 11 / 27 горимын хугацааг харьцуулна
```

| Сонголт | Утга |
|---|---|
| `-f ФАЙЛ` | Файлаас унших (`-` = stdin). 81 цифр (эхэнд UTF-8 BOM байж болно); хоосон зай, &#124; - + , үл тооцно; `.` эсвэл `0` = хоосон; `#` = тайлбар |
| `-g SEED` | SEED-ээр санамсаргүй зөв судоку үүсгэх |
| `-e K` | K нүдийг санамсаргүй өөр цифрээр солих |
| `-s R,C,V` | [R,C] нүдийг V болгох (давтаж болно) |
| `-t MODE` | `11` (анхдагч), `27`, `1` |
| `-b REPS` | Хурдны харьцуулалт |
| `-v` / `-q` | Дэлгэрэнгүй / зөвхөн дүн |

Гаралтын код: `0` = зөв, `1` = буруу, `2` = оролтын эсвэл системийн алдаа.

## Thread-ийн стратеги

| `-t` | Worker | Хуваарилалт |
|---|---|---|
| 11 | 11 | 1 бүх мөр, 1 бүх багана, 9 дэд тор (сурах бичгийн санал) |
| 27 | 27 | мөр бүрд 1, багана бүрд 1, дэд тор бүрд 1 |
| 1 | 1 | Бүх 27 бүсийг нэг worker (харьцуулах суурь) |

**Параметр дамжуулах.** Parent `parameters { row, column, count, index }` бүтцийг
`malloc`-оор үүсгэж `pthread_create()`-ийн 4-р аргументаар дамжуулна. `join` хийсний дараа `free` хийнэ.

**Үр дүн буцаах.** Глобал `int valid[N]`. i-р worker зөвхөн `valid[i]`-д бичдэг тул
mutex шаардлагагүй; `pthread_join()` нь бичилт parent-д харагдахыг баталгаажуулна.
Массив 0-ээр эхэлдэг тул ажиллаж чадаагүй worker автоматаар "буруу" гэж тооцогдоно.

**Шалгах арга.** Бүс бүрт 10 битийн mask: `v` цифр харагдвал `1<<v` бит асна.
Давхардал = бит аль хэдийн асаалттай. Эцэст нь `mask == 0x3FE` бол 1–9 бүгд байна.

## Тестийн үр дүн

`make test` нь C engine болон sanitizer binary-уудыг хөрвүүлж, автомат тест ажиллуулна. Орчноос хамаарч TSan/ASan ажиллах боломж өөр байж болно.

1. 13 файл/оролтын тохиолдол × 3 горим (зөв, нэг нүд буруу, зөвхөн дэд тор буруу,
   зөвхөн багана буруу, бүрэн бус, бүгд 5, 80 нүд, үсэгтэй, файл байхгүй, stdin, `-s`).
2. 27 горимд `valid[]` массив яг аль бүс буруу болохыг зөв заадаг эсэх.
3. 300 санамсаргүй судоку × 3 горим × (зөв + 1–5 алдаатай).
4. ThreadSanitizer, AddressSanitizer + UBSan: 50 судоку × 3 горим; үр дүнг тухайн CI run-ээс шалгана.
   Хяналтын туршилт: worker бүр `valid[0]`-д бичдэг болгож өөрчлөхөд TSan data race-ийг илрүүлсэн.

## Хурдны хэмжилт (`-b 2000`, 2 vCPU Linux, gcc 13.3 -O2)

| Горим | Thread | Дундаж (мкс) | Хамгийн бага (мкс) | 1 thread-тэй харьцуулахад |
|---|---|---|---|---|
| `-t 1` | 1 | 47.6 | 8.3 | 1.00× |
| `-t 11` | 11 | 291.7 | 162.3 | 6.12× удаан |
| `-t 27` | 27 | 672.4 | 415.9 | 14.12× удаан |

Нэг судоку шалгах ажил ~243 харьцуулалт буюу хэдхэн микросекунд. Thread үүсгэх, join хийх
зардал (~15–25 мкс/thread) түүнээс хэд дахин их тул энэ хэмжээний ажилд олон thread хурд нэмэхгүй.
Зэрэгцээ байдал нь ажил том үед (жишээ нь олон мянган судоку багцаар) ашигтай.

## Интерактив дүрслэл

`ui/sudoku_threads.html`-ийг хөтөч дээр нээнэ. Торыг засах, бэлэн жишээ, санамсаргүй
үүсгэх (C-ийн `-g`/`-e`-тэй ижил алгоритм), CPU цөм, `pthread_create` зардал, round-robin квант,
ready queue-ийн дараалал зэрэг параметрээр thread-ийн ажиллагааг симуляц хийж Gantt хуваарь,
`valid[]` массив, pthread лог, туршилтын бүртгэл (CSV), цөмийн тооны графикаар харуулна.

---

## Dashboard болон бэлэн хувилбарууд

Үндсэн интерфэйс нь `dashboard.html`. `server.py` нь локал HTTP bridge бөгөөд C/Pthreads хөдөлгүүрийг ажиллуулж бодит шалгалтын үр дүнг буцаана. `ui/sudoku_threads.html` нь тусдаа сургалтын симуляц.

### Windows — бэлэн EXE

[Build Windows standalone Sudoku](https://github.com/sumya4748-afk/Sudoku-Thread-Validator/actions/workflows/windows-release.yml) workflow-ийн хамгийн сүүлийн амжилттай run-ээс `SudokuValidation_Windows_Ready` artifact татна. ZIP-үүдийг задлаад `SudokuValidation.exe` ажиллуулна. Python болон GCC суулгах шаардлагагүй.

### macOS — бэлэн APP (Apple Silicon)

[Build macOS Sudoku app](https://github.com/sumya4748-afk/Sudoku-Thread-Validator/actions/workflows/macos-release.yml) workflow-ийн амжилттай run-ээс `SudokuValidation_Mac_Ready` artifact татна. ZIP-үүдийг задлаад `SudokuValidation.app` нээнэ. Apple Developer ID гарын үсэг/notarization байхгүй тул анх удаа **System Settings → Privacy & Security → Open Anyway** зөвшөөрөл шаардаж магадгүй. Intel Mac дээр шалгаагүй.

### macOS / Linux — эх кодоос

Python 3, C compiler, make шаардлагатай. Төслийн хавтсанд:

```sh
make clean && make
python3 server.py
```

Хөтөч дээр `http://127.0.0.1:8765/dashboard.html` нээнэ. Ubuntu/Debian-д эхлээд `sudo apt install build-essential python3` хэрэгтэй байж болно.

### Тест

```sh
python3 -m unittest discover -s tests -v
bash run_tests.sh
```

Windows, macOS, Linux-ийн CI шалгалтыг [GitHub Actions](https://github.com/sumya4748-afk/Sudoku-Thread-Validator/actions) хэсгээс харна. Тестийн тоо, benchmark үр дүн нь орчин, хувилбар бүрээр өөрчлөгдөж болно.

### Дэлгэрэнгүй заавар

[Хэрэглэгчийн гарын авлага](docs/USER_GUIDE.md). Dashboard-ийн **Алхмаар үзүүлэх** нь C-ээс буцсан үр дүнг тайлбарлан дахин тоглуулдаг; OS thread scheduler-ийн live trace биш. Сервер зөвхөн `127.0.0.1` дээр ажиллана.
