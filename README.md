# Sudoku Solution Validator (Pthreads)

9×9 судокугийн шийдэл зөв эсэхийг олон worker thread-ээр зэрэгцээ шалгана.

## Бүтэц

| Файл | Агуулга |
|---|---|
| `sudoku_validator.c` | Үндсэн программ (C11 + Pthreads; build-д ашиглагддаг үндсэн файл) |
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

**Үр дүн буцаах.** Глобал `int valid[MAX_WORKERS]` (`MAX_WORKERS = 27`). i-р worker зөвхөн `valid[i]`-д бичдэг тул
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

**Энгийн Windows хэрэглэгчдэд санал болгох арга:** [Windows ZIP-ийг шууд татах](https://github.com/sumya4748-afk/Sudoku-Thread-Validator/releases/download/windows-latest/SudokuValidation_Windows_Ready.zip) (эсвэл [Releases хуудас](https://github.com/sumya4748-afk/Sudoku-Thread-Validator/releases/tag/windows-latest)). `SudokuValidation_Windows_Ready.zip`-ийг татаж, **Extract All** хийж бүрэн задлаад, доторх `SudokuValidation.exe`-г ажиллуулна. ZIP дотроос нь шууд HTML нээхгүй. Python болон GCC суулгах шаардлагагүй. Windows SmartScreen анхааруулга өгч болзошгүй; зөвхөн итгэлтэй эх сурвалжаас татсан файлыг ажиллуулна.

**Эх кодоос ажиллуулах хуучин арга:** `START_WINDOWS.bat` нь GitHub-ийн **Code → Download ZIP**-ээр авсан эх кодын багцад хэвээр байна. Энэ арга нь Python болон C compiler (GCC) шаарддаг тул хөгжүүлэгч, багш, эх кодыг шалгах хүмүүст зориулагдсан. Энгийн хэрэглэгчид `.bat` ажиллуулах шаардлагагүй. `windows-release.yml` нь Windows EXE-г автоматаар build хийж шалгаад, `windows-latest` Release-д ZIP-г нийтэлдэг тохиргоо; хэрэглэгчид энэ YAML файлыг татахгүй.

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

## AI хэрэгслийн ашиглалт

Төслийн C/Pthreads код, интерфэйс, автомат тест болон баримтжуулалтыг боловсруулах, алдаа засах явцад ChatGPT (OpenAI)-ийн тусламж ашигласан. Программын ажиллагааг автомат тестээр шалгаж, үр дүнг GitHub Actions-д баталгаажуулсан.

## Багшийн UI шаардлагатай нийцүүлсэн тайлбар

- **Бодит шалгалт:** `dashboard.html` нь `server.py`-ээр дамжин C/Pthreads хөдөлгүүрийг ажиллуулж, Sudoku-ийн мөр, багана, 3×3 дэд хүснэгтийн шалгалтын үр дүнг харуулна. Энэ нь төслийн үндсэн ажиллах UI юм.
- **Сургалтын симуляц:** `ui/sudoku_threads.html` дахь CPU core, ready queue, Gantt болон tick-ийн дүрслэл нь thread scheduling-ийн **загварчилсан** тайлбар бөгөөд бодит үйлдлийн системийн scheduler trace эсвэл C thread-үүдийн хэмжсэн хугацаа биш.
- **Хугацааны хэмжилт:** Бодит benchmark-ийн тоонуудыг C engine-ээс авна; симуляцын tick-тэй харьцуулж бодит хэмжилт гэж үзэхгүй.

**Repository бүтэц:** `src/sudoku_validator.c` нь root дахь `sudoku_validator.c`-ийн ижил агуулгатай хуулбар. Одоогийн build, CI, Windows/macOS багцууд root дахь файлыг ашигласан хэвээр тул ажиллаж буй замуудыг өөрчлөөгүй. Код өөрчлөхдөө хоёр файлыг ижил байлгах шаардлагатай; бүрэн шилжүүлэлт хийгдээгүй.

**Тайлангийн тэмдэглэл:** [AI ашиглалт ба бодит UI/симуляцын ялгаа](docs/REPORT_AI_UI_NOTES.md) — энэ тайлбарыг үндсэн `docs/Report.pdf`-д нэгтгэх шаардлагатай.
