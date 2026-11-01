/*
 * sudoku_validator.c
 * Operating System Concepts, Chapter 4 — Programming Project 1:
 * Sudoku Solution Validator (Pthreads)
 *
 * 9x9 судокугийн шийдэл зөв эсэхийг олон worker thread-ээр зэрэгцээ шалгана.
 *
 * Thread-ийн стратеги (-t):
 *   11 : 1 thread бүх мөрийг, 1 thread бүх баганыг, 9 thread дэд торыг
 *        (сурах бичгийн санал болгосон хувилбар, нийт 11 thread)
 *   27 : мөр бүрд 1, багана бүрд 1, дэд тор бүрд 1 thread (нийт 27 thread)
 *    1 : бүх шалгалтыг ганц worker thread хийнэ (харьцуулах суурь)
 *
 * Параметр дамжуулах: parent thread `parameters` бүтцийг malloc-оор үүсгэж,
 *   pthread_create()-ийн 4-р аргументаар worker-т дамжуулна.
 * Үр дүн буцаах: бүх thread-д харагдах `valid[]` массив. i-р worker зөвхөн
 *   valid[i]-д бичнэ (1 = зөв, 0 = буруу). Parent pthread_join()-оор бүгдийг
 *   хүлээсний дараа массивыг уншиж эцсийн шийдвэр гаргана.
 *
 * Хөрвүүлэх: make            (эсвэл gcc -Wall -O2 -pthread sudoku_validator.c -o sudoku_validator)
 * Ажиллуулах: ./sudoku_validator -h
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define N 9
#define MAX_WORKERS 27
#define MAX_ISSUES (3 * N * 18) /* 27 бүс × бүс бүрд дээд тал нь 18 асуудал (9 хоосон + 9 дутуу) */
#define FULL_MASK 0x3FEu /* 1..9 битүүд асаалттай = бүх цифр байгаа */

/* ---------- Thread-д дамжуулах өгөгдөл (сурах бичгийн бүтцийг өргөтгөв) ---------- */
typedef struct {
    int row;    /* шалгаж эхлэх мөр (0-ээс) */
    int column; /* шалгаж эхлэх багана (0-ээс) */
    int count;  /* дараалсан хэдэн мөр/багана шалгах (дэд торд хэрэглэхгүй) */
    int index;  /* энэ worker-ийн valid[] массив дахь байрлал */
} parameters;

/* ---------- Оношлогооны мэдээлэл ---------- */
typedef enum { REG_ROW, REG_COL, REG_BOX } region_t;
typedef enum { ISSUE_DUP, ISSUE_RANGE, ISSUE_MISSING } issue_kind;

typedef struct {
    region_t region;
    int region_no; /* 0..8 */
    issue_kind kind;
    int digit;
    int r, c; /* асуудалтай нүд; ISSUE_MISSING үед -1 */
} issue;

typedef struct {
    char name[96]; /* UTF-8 кирилл үсэг 2 байт тул илүү зай */
    int n_issues;
    issue issues[MAX_ISSUES];
} worker_report;

/* ---------- Thread бүрт харагдах хуваалцсан өгөгдөл ---------- */
static int sudoku[N][N];                 /* worker-ууд зөвхөн уншина */
static int valid[MAX_WORKERS];           /* i-р worker зөвхөн valid[i]-д бичнэ */
static worker_report reports[MAX_WORKERS]; /* i-р worker зөвхөн reports[i]-д бичнэ */
static int verbose = 0;
static int quiet = 0;
static int use_color = 0;

/* Сурах бичгийн Figure 4.26 дахь зөв шийдэл (анхдагч оролт) */
static const int figure_4_26[N][N] = {
    {6, 2, 4, 5, 3, 9, 1, 8, 7}, {5, 1, 9, 7, 2, 8, 6, 3, 4}, {8, 3, 7, 6, 1, 4, 2, 9, 5},
    {1, 4, 3, 8, 6, 5, 7, 2, 9}, {9, 5, 8, 2, 4, 7, 3, 6, 1}, {7, 6, 2, 3, 9, 1, 4, 5, 8},
    {3, 7, 1, 9, 5, 6, 8, 4, 2}, {4, 9, 6, 1, 8, 2, 5, 7, 3}, {2, 8, 5, 4, 7, 3, 9, 1, 6},
};

/* region-ийн k-р нүдний координат */
static void cell_of(region_t reg, int no, int k, int *r, int *c) {
    switch (reg) {
    case REG_ROW: *r = no; *c = k; break;
    case REG_COL: *r = k; *c = no; break;
    default: /* REG_BOX */ *r = (no / 3) * 3 + k / 3; *c = (no % 3) * 3 + k % 3; break;
    }
}

static void add_issue(worker_report *rep, region_t reg, int no, issue_kind kind, int digit, int r, int c) {
    if (rep->n_issues >= MAX_ISSUES) return;
    issue *is = &rep->issues[rep->n_issues++];
    is->region = reg; is->region_no = no; is->kind = kind;
    is->digit = digit; is->r = r; is->c = c;
}

/* Нэг бүс (мөр/багана/дэд тор) 1..9 цифрийг яг нэг удаа агуулж байгаа эсэх.
 * Bitmask ашиглана: v цифр харагдвал (1<<v) битийг асаана. */
static int check_region(region_t reg, int no, worker_report *rep) {
    unsigned mask = 0;
    int ok = 1;
    for (int k = 0; k < N; k++) {
        int r, c;
        cell_of(reg, no, k, &r, &c);
        int v = sudoku[r][c];
        if (v < 1 || v > 9) {
            ok = 0;
            add_issue(rep, reg, no, ISSUE_RANGE, v, r, c);
            continue;
        }
        if (mask & (1u << v)) {
            ok = 0;
            add_issue(rep, reg, no, ISSUE_DUP, v, r, c);
        }
        mask |= 1u << v;
    }
    if (mask != FULL_MASK) {
        ok = 0;
        for (int d = 1; d <= 9; d++)
            if (!(mask & (1u << d))) add_issue(rep, reg, no, ISSUE_MISSING, d, -1, -1);
    }
    return ok;
}

static void trace_start(const parameters *p) {
    if (verbose)
        printf("  [worker #%-2d] эхэллээ   : %s\n", p->index, reports[p->index].name);
}
static void trace_end(const parameters *p, int ok) {
    if (verbose)
        printf("  [worker #%-2d] дууслаа   : valid[%d] = %d\n", p->index, p->index, ok);
}

/* ---------- Worker thread-ийн функцууд ---------- */

/* p->row-оос эхлэн p->count ширхэг мөрийг шалгана */
static void *check_rows(void *arg) {
    parameters *p = (parameters *)arg;
    trace_start(p);
    int ok = 1;
    for (int r = p->row; r < p->row + p->count; r++)
        ok &= check_region(REG_ROW, r, &reports[p->index]);
    valid[p->index] = ok; /* үр дүнг parent-д буцаах */
    trace_end(p, ok);
    pthread_exit(NULL);
}

/* p->column-оос эхлэн p->count ширхэг баганыг шалгана */
static void *check_columns(void *arg) {
    parameters *p = (parameters *)arg;
    trace_start(p);
    int ok = 1;
    for (int c = p->column; c < p->column + p->count; c++)
        ok &= check_region(REG_COL, c, &reports[p->index]);
    valid[p->index] = ok;
    trace_end(p, ok);
    pthread_exit(NULL);
}

/* (p->row, p->column) зүүн дээд булантай 3x3 дэд торыг шалгана */
static void *check_subgrid(void *arg) {
    parameters *p = (parameters *)arg;
    trace_start(p);
    int box = (p->row / 3) * 3 + p->column / 3;
    int ok = check_region(REG_BOX, box, &reports[p->index]);
    valid[p->index] = ok;
    trace_end(p, ok);
    pthread_exit(NULL);
}

/* Харьцуулах суурь: 27 бүсийг бүгдийг нь ганц thread шалгана */
static void *check_all(void *arg) {
    parameters *p = (parameters *)arg;
    trace_start(p);
    int ok = 1;
    for (int i = 0; i < N; i++) {
        ok &= check_region(REG_ROW, i, &reports[p->index]);
        ok &= check_region(REG_COL, i, &reports[p->index]);
        ok &= check_region(REG_BOX, i, &reports[p->index]);
    }
    valid[p->index] = ok;
    trace_end(p, ok);
    pthread_exit(NULL);
}

/* ---------- Thread-ийн төлөвлөгөө ---------- */
typedef void *(*worker_fn)(void *);
typedef struct {
    worker_fn fn;
    int row, column, count;
    const char *kind;
} plan_item;

static int build_plan(int mode, plan_item *plan) {
    int n = 0;
    if (mode == 1) {
        plan[n++] = (plan_item){check_all, 0, 0, 9, "all"};
        snprintf(reports[0].name, sizeof reports[0].name, "бүх 27 бүс");
        return n;
    }
    if (mode == 11) {
        snprintf(reports[n].name, sizeof reports[n].name, "бүх мөр (1-9)");
        plan[n++] = (plan_item){check_rows, 0, 0, 9, "rows"};
        snprintf(reports[n].name, sizeof reports[n].name, "бүх багана (1-9)");
        plan[n++] = (plan_item){check_columns, 0, 0, 9, "columns"};
    } else { /* 27 */
        for (int r = 0; r < N; r++) {
            snprintf(reports[n].name, sizeof reports[n].name, "мөр %d", r + 1);
            plan[n++] = (plan_item){check_rows, r, 0, 1, "row"};
        }
        for (int c = 0; c < N; c++) {
            snprintf(reports[n].name, sizeof reports[n].name, "багана %d", c + 1);
            plan[n++] = (plan_item){check_columns, 0, c, 1, "column"};
        }
    }
    for (int b = 0; b < N; b++) {
        int r0 = (b / 3) * 3, c0 = (b % 3) * 3;
        snprintf(reports[n].name, sizeof reports[n].name, "дэд тор %d (мөр %d-%d, багана %d-%d)",
                 b + 1, r0 + 1, r0 + 3, c0 + 1, c0 + 3);
        plan[n++] = (plan_item){check_subgrid, r0, c0, 1, "subgrid"};
    }
    return n;
}

/* Parent thread: worker-уудыг үүсгэж, хүлээж, valid[]-ийг нэгтгэнэ.
 * Буцаах утга: 1 = судоку зөв, 0 = буруу. elapsed_us-д хугацааг бичнэ. */
static int run_validation(int mode, int *n_workers, double *elapsed_us) {
    plan_item plan[MAX_WORKERS];
    pthread_t tids[MAX_WORKERS];
    parameters *params[MAX_WORKERS];

    memset(reports, 0, sizeof reports);
    int n = build_plan(mode, plan);
    for (int i = 0; i < n; i++) valid[i] = 0; /* fail-safe: ажиллаагүй worker = буруу */

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    for (int i = 0; i < n; i++) {
        parameters *data = (parameters *)malloc(sizeof(parameters));
        if (!data) { perror("malloc"); exit(2); }
        data->row = plan[i].row;
        data->column = plan[i].column;
        data->count = plan[i].count;
        data->index = i;
        params[i] = data;
        if (verbose)
            printf("[main] pthread_create #%-2d %-8s row=%d column=%d count=%d\n",
                   i, plan[i].kind, data->row, data->column, data->count);
        /* Thread үүсгэж, data-г параметр болгон дамжуулна */
        int rc = pthread_create(&tids[i], NULL, plan[i].fn, data);
        if (rc != 0) {
            fprintf(stderr, "pthread_create алдаа (#%d): %s\n", i, strerror(rc));
            exit(2);
        }
    }

    for (int i = 0; i < n; i++) {
        int rc = pthread_join(tids[i], NULL);
        if (rc != 0) fprintf(stderr, "pthread_join алдаа (#%d): %s\n", i, strerror(rc));
        free(params[i]);
    }
    if (verbose) printf("[main] бүх %d worker pthread_join-оор дууслаа\n", n);

    clock_gettime(CLOCK_MONOTONIC, &t1);
    if (elapsed_us)
        *elapsed_us = (t1.tv_sec - t0.tv_sec) * 1e6 + (t1.tv_nsec - t0.tv_nsec) / 1e3;
    if (n_workers) *n_workers = n;

    /* Parent: үр дүнгийн массивыг шалгах */
    int all_ok = 1;
    for (int i = 0; i < n; i++)
        if (valid[i] != 1) all_ok = 0;
    return all_ok;
}

/* ---------- Оролт ---------- */
static int check_line_shape(int line, int cells) {
    if (cells != 0 && cells != N && cells != N * N) {
        fprintf(stderr, "Оролтын алдаа (мөр %d): мөрөнд 9 нүд (эсвэл бүх 81 нүд нэг мөрөнд) хүлээж байсан, %d олдлоо\n",
                line, cells);
        return -1;
    }
    return 0;
}

static int load_grid(const char *path) {
    int is_stdin = strcmp(path, "-") == 0;
    struct stat st;
    if (!is_stdin && stat(path, &st) == 0 && S_ISDIR(st.st_mode)) {
        fprintf(stderr, "Оролтын алдаа: '%s' нь хавтас, файл биш\n", path);
        return -1;
    }
    FILE *f = is_stdin ? stdin : fopen(path, "r");
    if (!f) { perror(path); return -1; }
    int count = 0, ch, line = 1, in_comment = 0, cells = 0, rc = 0;
    /* Accept an optional UTF-8 BOM only at the beginning of the input. */
    ch = fgetc(f);
    if (ch == 0xEF) {
        int second = fgetc(f), third = fgetc(f);
        if (second == 0xBB && third == 0xBF) {
            ch = fgetc(f);
        } else {
            fprintf(stderr, "Оролтын алдаа: UTF-8 BOM буруу байна\\n");
            rc = -1;
            ch = EOF;
        }
    }
    while (rc == 0 && ch != EOF) {
        if (ch == '\n') {
            if (check_line_shape(line, cells) != 0) { rc = -1; break; }
            line++; in_comment = 0; cells = 0; { ch = fgetc(f); continue; }
        }
        if (in_comment) { ch = fgetc(f); continue; }
        if (ch == '#') { in_comment = 1; { ch = fgetc(f); continue; } }
        if (ch == ' ' || ch == '\t' || ch == '\r' || ch == ',' || ch == '|' ||
            ch == '-' || ch == '+' || ch == ';')
            { ch = fgetc(f); continue; }
        int v;
        if (ch >= '0' && ch <= '9') v = ch - '0';
        else if (ch == '.' || ch == '_') v = 0;
        else {
            fprintf(stderr, "Оролтын алдаа (мөр %d): '%c' тэмдэгт буруу\n", line, ch);
            rc = -1; break;
        }
        if (count >= N * N) {
            fprintf(stderr, "Оролтын алдаа: 81-ээс олон нүд байна\n");
            rc = -1; break;
        }
        sudoku[count / N][count % N] = v;
        count++; cells++;
        ch = fgetc(f);
    }
    if (rc == 0 && check_line_shape(line, cells) != 0) rc = -1;
    if (!is_stdin) fclose(f);
    if (rc != 0) return -1;
    if (count != N * N) {
        fprintf(stderr, "Оролтын алдаа: 81 нүд хүлээж байсан, %d олдлоо\n", count);
        return -1;
    }
    return 0;
}

/* ---------- Санамсаргүй судоку үүсгэх (xorshift32, seed-ээр давтагдана) ---------- */
static uint32_t rng_state = 0x9E3779B9u;
static uint32_t rnd(void) {
    uint32_t x = rng_state;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    return rng_state = x;
}
static int rnd_below(int n) { return (int)(rnd() % (uint32_t)n); }
static void shuffle(int *a, int n) {
    for (int i = n - 1; i > 0; i--) {
        int j = rnd_below(i + 1), t = a[i];
        a[i] = a[j]; a[j] = t;
    }
}

/* Үндсэн хэв (3*(r%3) + r/3 + c) mod 9 нь үргэлж зөв судоку. Цифр, бүсийн доторх
 * мөр/багана, бүсүүдийг холих нь зөв байдлыг хадгална. */
static void generate(uint32_t seed) {
    rng_state = seed ? seed : 0x9E3779B9u;
    for (int i = 0; i < 8; i++) rnd(); /* жижиг seed-ийн нөлөөг арилгах */
    int digits[9] = {1, 2, 3, 4, 5, 6, 7, 8, 9}, rows[9], cols[9];
    shuffle(digits, 9);
    int band[3] = {0, 1, 2}, stack[3] = {0, 1, 2};
    shuffle(band, 3); shuffle(stack, 3);
    for (int b = 0; b < 3; b++) {
        int in_r[3] = {0, 1, 2}, in_c[3] = {0, 1, 2};
        shuffle(in_r, 3); shuffle(in_c, 3);
        for (int k = 0; k < 3; k++) {
            rows[b * 3 + k] = band[b] * 3 + in_r[k];
            cols[b * 3 + k] = stack[b] * 3 + in_c[k];
        }
    }
    for (int r = 0; r < N; r++)
        for (int c = 0; c < N; c++)
            sudoku[r][c] = digits[(3 * (rows[r] % 3) + rows[r] / 3 + cols[c]) % 9];
}

/* k ширхэг өөр нүдийг санамсаргүй өөр цифрээр солих (алдаа оруулах) */
static void inject_errors(int k) {
    int used[N * N] = {0};
    if (k > N * N) k = N * N;
    for (int i = 0; i < k; i++) {
        int pos;
        do { pos = rnd_below(N * N); } while (used[pos]);
        used[pos] = 1;
        int r = pos / N, c = pos % N, old = sudoku[r][c], v;
        do { v = 1 + rnd_below(9); } while (v == old);
        sudoku[r][c] = v;
        if (!quiet) printf("  алдаа оруулав: нүд [%d,%d] %d -> %d\n", r + 1, c + 1, old, v);
    }
}

/* ---------- Хэвлэх ---------- */
static const char *region_name(region_t r) {
    return r == REG_ROW ? "мөр" : r == REG_COL ? "багана" : "дэд тор";
}

static void mark_bad_cells(int bad[N][N], int n_workers) {
    for (int w = 0; w < n_workers; w++)
        for (int i = 0; i < reports[w].n_issues; i++) {
            issue *is = &reports[w].issues[i];
            if (is->kind == ISSUE_RANGE) bad[is->r][is->c] = 1;
            if (is->kind == ISSUE_DUP)
                for (int k = 0; k < N; k++) {
                    int r, c;
                    cell_of(is->region, is->region_no, k, &r, &c);
                    if (sudoku[r][c] == is->digit) bad[r][c] = 1;
                }
        }
}

static void print_grid(int bad[N][N]) {
    for (int r = 0; r < N; r++) {
        if (r % 3 == 0) printf("  +-------+-------+-------+\n");
        printf("  ");
        for (int c = 0; c < N; c++) {
            if (c % 3 == 0) printf("| ");
            int v = sudoku[r][c];
            char ch = v >= 1 && v <= 9 ? (char)('0' + v) : '.';
            if (bad && bad[r][c]) {
                if (use_color) printf("\033[1;31m%c\033[0m ", ch);
                else printf("%c*", ch);
            } else {
                printf("%c ", ch);
            }
        }
        printf("|\n");
    }
    printf("  +-------+-------+-------+\n");
}

static void print_issue(const issue *is) {
    const char *rn = region_name(is->region);
    switch (is->kind) {
    case ISSUE_DUP:
        printf("        - %s %d: %d цифр давхардсан (нүд [%d,%d])\n", rn, is->region_no + 1,
               is->digit, is->r + 1, is->c + 1);
        break;
    case ISSUE_RANGE:
        printf("        - %s %d: нүд [%d,%d] = %d (1-9 биш / хоосон)\n", rn, is->region_no + 1,
               is->r + 1, is->c + 1, is->digit);
        break;
    case ISSUE_MISSING:
        printf("        - %s %d: %d цифр дутуу\n", rn, is->region_no + 1, is->digit);
        break;
    }
}

static void print_results(int n_workers) {
    printf("\n  Thread  valid[i]  Шалгасан бүс\n");
    printf("  ------  --------  ------------------------------------\n");
    for (int i = 0; i < n_workers; i++) {
        printf("  #%-5d  %-8d  %s\n", i, valid[i], reports[i].name);
        int shown = 0;
        for (int k = 0; k < reports[i].n_issues; k++) {
            if (reports[i].issues[k].kind == ISSUE_MISSING) continue; /* давхардлаас үүдэлтэй */
            if (shown++ < 6) print_issue(&reports[i].issues[k]);
        }
        if (shown > 6) printf("        ... дахиад %d асуудал\n", shown - 6);
    }
}

/* Бүхэл тоон аргументыг чанд шалгана (atoi шиг чимээгүй 0 болгохгүй) */
static int parse_num(const char *opt, const char *str, long long lo, long long hi, long long *out) {
    char *end;
    errno = 0;
    long long v = strtoll(str, &end, 10);
    if (str[0] == '\0' || *end != '\0' || errno == ERANGE || v < lo || v > hi) {
        fprintf(stderr, "-%s буруу: '%s' (%lld-%lld хоорондох бүхэл тоо байх ёстой)\n", opt, str, lo, hi);
        return -1;
    }
    *out = v;
    return 0;
}

static void usage(const char *prog) {
    printf(
        "Хэрэглээ: %s [сонголтууд]\n"
        "  -f ФАЙЛ   судокуг файлаас унших ('-' = stdin). 81 цифр; хоосон зай, | - + , үл тооцно,\n"
        "            '.' эсвэл 0 = хоосон нүд, '#'-ээс мөрийн төгсгөл хүртэл тайлбар\n"
        "  -g SEED   SEED-ээр санамсаргүй ЗӨВ судоку үүсгэх (0-4294967295; -f-тэй хамт хэрэглэхгүй)\n"
        "  -e K      K (0-81) ширхэг санамсаргүй нүдийг өөр цифрээр солих (алдаа оруулах)\n"
        "  -s R,C,V  [R,C] нүдийг V болгох (1-ээс тоолно, давтаж болно)\n"
        "  -t MODE   thread-ийн стратеги: 11 (анхдагч), 27, 1\n"
        "  -b REPS   1 / 11 / 27 горимыг REPS (1-1000000) удаа ажиллуулж хугацаа харьцуулах\n"
        "  -v        thread бүрийн үүсгэлт, эхлэл, төгсгөлийг хэвлэх\n"
        "  -q        зөвхөн эцсийн дүнг хэвлэх\n"
        "  -h        энэ тусламж\n"
        "Оролт өгөөгүй бол сурах бичгийн Figure 4.26-ийн жишээг ашиглана.\n"
        "Гаралтын код: 0 = зөв, 1 = буруу, 2 = оролт/системийн алдаа\n",
        prog);
}

int main(int argc, char *argv[]) {
    const char *file = NULL;
    long long seed = -1, num;
    int errors = 0, mode = 11, bench = 0;
    int sets[N * N][3], n_sets = 0;
    int opt;

    while ((opt = getopt(argc, argv, "f:g:e:s:t:b:vqh")) != -1) {
        switch (opt) {
        case 'f':
            if (file) { fprintf(stderr, "-f нэг л удаа өгөгдөнө\n"); return 2; }
            file = optarg; break;
        case 'g':
            if (seed >= 0) { fprintf(stderr, "-g нэг л удаа өгөгдөнө\n"); return 2; }
            if (parse_num("g", optarg, 0, 4294967295LL, &num)) return 2;
            seed = num; break;
        case 'e': if (parse_num("e", optarg, 0, N * N, &num)) return 2; errors = (int)num; break;
        case 's': {
            int r, c, v, parsed[3];
            const char *cursor = optarg;
            int good = 1;
            for (int field = 0; field < 3; field++) {
                char *end = NULL;
                errno = 0;
                if (*cursor < '0' || *cursor > '9') { good = 0; break; }
                long value = strtol(cursor, &end, 10);
                if (errno == ERANGE || end == cursor || value < (field == 2 ? 0 : 1) || value > 9) {
                    good = 0; break;
                }
                parsed[field] = (int)value;
                if (field < 2) {
                    if (*end != ',') { good = 0; break; }
                    cursor = end + 1;
                } else if (*end != '\0') {
                    good = 0;
                }
            }
            if (good) { r = parsed[0]; c = parsed[1]; v = parsed[2]; }
            if (!good) {
                fprintf(stderr, "-s буруу: '%s' (жишээ: -s 3,5,7)\n", optarg);
                return 2;
            }
            if (n_sets < N * N) { sets[n_sets][0] = r - 1; sets[n_sets][1] = c - 1; sets[n_sets][2] = v; n_sets++; }
            else { fprintf(stderr, "-s хэт олон (дээд тал нь 81)\n"); return 2; }
            break;
        }
        case 't': if (parse_num("t", optarg, 1, 27, &num)) return 2; mode = (int)num; break;
        case 'b': if (parse_num("b", optarg, 1, 1000000, &num)) return 2; bench = (int)num; break;
        case 'v': verbose = 1; break;
        case 'q': quiet = 1; break;
        case 'h': usage(argv[0]); return 0;
        default: usage(argv[0]); return 2;
        }
    }
    if (optind < argc) { fprintf(stderr, "Ойлгомжгүй аргумент: '%s' (тусламж: -h)\n", argv[optind]); return 2; }
    if (file && seed >= 0) { fprintf(stderr, "-f болон -g хамт хэрэглэх боломжгүй (оролтын эх хоёр байна)\n"); return 2; }
    if (mode != 1 && mode != 11 && mode != 27) {
        fprintf(stderr, "-t зөвхөн 1, 11, 27 байж болно\n");
        return 2;
    }
    use_color = isatty(STDOUT_FILENO);

    /* --- Оролт бэлтгэх --- */
    const char *source;
    if (file) {
        if (load_grid(file) != 0) return 2;
        source = file;
    } else if (seed >= 0) {
        generate((uint32_t)seed);
        source = "санамсаргүй үүсгэсэн";
    } else {
        memcpy(sudoku, figure_4_26, sizeof sudoku);
        source = "Figure 4.26 (сурах бичиг)";
    }
    if (errors > 0) {
        if (seed < 0) rng_state = (uint32_t)time(NULL) | 1u;
        inject_errors(errors);
    }
    for (int i = 0; i < n_sets; i++) {
        if (!quiet)
            printf("  нүд [%d,%d] %d -> %d\n", sets[i][0] + 1, sets[i][1] + 1,
                   sudoku[sets[i][0]][sets[i][1]], sets[i][2]);
        sudoku[sets[i][0]][sets[i][1]] = sets[i][2];
    }

    /* --- Хурдны харьцуулалт --- */
    if (bench > 0) {
        int saved_verbose = verbose;
        verbose = 0;
        int modes[3] = {1, 11, 27};
        double base_avg = 0;
        printf("Хурдны харьцуулалт: %d давталт, оролт: %s\n", bench, source);
        printf("  Горим   Thread  Дундаж(мкс)  Хамгийн бага  Хамгийн их  Харьцаа  Дүн\n");
        for (int m = 0; m < 3; m++) {
            double sum = 0, mn = 1e18, mx = 0, us;
            int nw = 0, res = 0;
            for (int k = 0; k < bench; k++) {
                res = run_validation(modes[m], &nw, &us);
                sum += us;
                if (us < mn) mn = us;
                if (us > mx) mx = us;
            }
            double avg = sum / bench;
            if (m == 0) base_avg = avg;
            printf("  -t %-4d %-6d  %11.2f  %12.2f  %10.2f  %6.2fx  %s\n", modes[m], nw, avg, mn, mx,
                   avg / base_avg, res ? "ЗӨВ" : "БУРУУ");
        }
        printf("  (Харьцаа = тухайн горимын дундаж хугацаа / 1-thread горимын дундаж хугацаа)\n");
        verbose = saved_verbose;
        return 0;
    }

    /* --- Шалгалт --- */
    if (!quiet) {
        printf("Оролт: %s\n", source);
        print_grid(NULL);
        printf("\nСтратеги: -t %d\n", mode);
    }
    int n_workers;
    double us;
    int ok = run_validation(mode, &n_workers, &us);

    if (!quiet) {
        print_results(n_workers);
        if (!ok) {
            int bad[N][N] = {{0}};
            mark_bad_cells(bad, n_workers);
            printf("\n  Зөрчилтэй нүднүүд (%s):\n", use_color ? "улаанаар" : "* тэмдэгтэй");
            print_grid(bad);
        }
        int n_ok = 0;
        for (int i = 0; i < n_workers; i++) n_ok += valid[i];
        printf("\n  valid[] = [");
        for (int i = 0; i < n_workers; i++) printf("%d%s", valid[i], i + 1 < n_workers ? " " : "");
        printf("]  (%d/%d worker зөв)\n", n_ok, n_workers);
        printf("  Хугацаа: %.1f мкс (%d thread үүсгэх + join)\n", us, n_workers);
    }
    printf("ДҮН: Судокугийн шийдэл %s\n", ok ? "ЗӨВ" : "БУРУУ");
    return ok ? 0 : 1;
}
