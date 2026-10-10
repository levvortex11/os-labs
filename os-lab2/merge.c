#define _POSIX_C_SOURCE 200809L
#include <pthread.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

typedef struct { int *src, *dst; size_t n, width, id, workers; unsigned hold; } Task;

static void *merge_worker(void *arg) {
    Task *t = arg;
    if (t->hold) { struct timespec d = {(time_t)t->hold, 0}; while (nanosleep(&d, &d) && errno == EINTR) {} }
    size_t step = t->width * 2;
    size_t jobs = (t->n + step - 1) / step;
    for (size_t job = t->id; job < jobs; job += t->workers) {
        size_t lo = job * step, mid = lo + t->width, hi = lo + step;
        if (mid > t->n) mid = t->n;
        if (hi > t->n) hi = t->n;
        size_t a = lo, b = mid;
        for (size_t k = lo; k < hi; ++k)
            t->dst[k] = (a < mid && (b == hi || t->src[a] <= t->src[b])) ? t->src[a++] : t->src[b++];
    }
    return NULL;
}

static int sort(int *a, size_t n, size_t limit, unsigned hold) {
    if (n < 2) return 0;
    int *tmp = malloc(n * sizeof *tmp);
    pthread_t *threads = calloc(limit > 1 ? limit - 1 : 1, sizeof *threads);
    Task *tasks = calloc(limit, sizeof *tasks);
    if (!tmp || !threads || !tasks) { fprintf(stderr, "Out of memory\n"); free(tmp); free(threads); free(tasks); return -1; }
    int *src = a, *dst = tmp, failed = 0;
    for (size_t width = 1; width < n; width *= 2) {
        size_t jobs = (n + 2 * width - 1) / (2 * width);
        size_t count = jobs < limit ? jobs : limit, started = 0;
        for (size_t i = 0; i < count; ++i) tasks[i] = (Task){src, dst, n, width, i, count, hold};
        for (size_t i = 1; i < count; ++i) {
            int e = pthread_create(&threads[i - 1], NULL, merge_worker, &tasks[i]);
            if (e) { fprintf(stderr, "pthread_create: %s\n", strerror(e)); failed = 1; break; }
            ++started;
        }
        if (!failed) merge_worker(&tasks[0]);
        for (size_t i = 0; i < started; ++i) {
            int e = pthread_join(threads[i], NULL);
            if (e) { fprintf(stderr, "pthread_join: %s\n", strerror(e)); exit(1); }
        }
        if (failed) break;
        int *swap = src; src = dst; dst = swap;
        hold = 0;
    }
    if (!failed && src != a) memcpy(a, src, n * sizeof *a);
    free(tmp); free(threads); free(tasks); return failed ? -1 : 0;
}

static int number(const char *s, size_t *v) {
    if (!*s || *s == '-') return -1;
    errno = 0; char *end; unsigned long long x = strtoull(s, &end, 10);
    if (errno || *end || x > SIZE_MAX) return -1;
    *v = (size_t)x; return 0;
}
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (double)t.tv_sec + (double)t.tv_nsec / 1e9; }
int main(int argc, char **argv) {
    size_t limit = 1, n = 0, seed = 1, hold = 0; int generated = 0, quiet = 0;
    const char *pattern = "random";
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--quiet")) { quiet = 1; continue; }
        if (i + 1 >= argc) { fprintf(stderr, "Missing argument: %s\n", argv[i]); return 1; }
        const char *key = argv[i++], *value = argv[i];
        if (!strcmp(key, "--pattern")) pattern = value;
        else if (!strcmp(key, "--threads")) { if (number(value, &limit) || !limit || limit > 256) goto bad; }
        else if (!strcmp(key, "--size")) { if (number(value, &n)) goto bad; generated = 1; }
        else if (!strcmp(key, "--seed")) { if (number(value, &seed) || seed > UINT32_MAX) goto bad; }
        else if (!strcmp(key, "--hold")) { if (number(value, &hold) || hold > 300) goto bad; }
        else goto bad;
    }
    if (strcmp(pattern, "random") && strcmp(pattern, "sorted") && strcmp(pattern, "reverse")) goto bad;
    if (!generated) {
        unsigned long long input;
        if (scanf("%llu", &input) != 1 || input > SIZE_MAX) { fprintf(stderr, "Expected array length\n"); return 1; }
        n = (size_t)input;
    }
    if (n > SIZE_MAX / sizeof(int) / 2 || n > INT_MAX) { fprintf(stderr, "Array too large\n"); return 1; }
    int *a = malloc((n ? n : 1) * sizeof *a);
    if (!a) { fprintf(stderr, "Out of memory\n"); return 1; }
    uint32_t state = (uint32_t)seed;
    for (size_t i = 0; i < n; ++i) {
        if (!generated) { if (scanf("%d", &a[i]) != 1) { fprintf(stderr, "Expected %zu integers\n", n); free(a); return 1; } }
        else if (!strcmp(pattern, "sorted")) a[i] = (int)i;
        else if (!strcmp(pattern, "reverse")) a[i] = (int)(n - i);
        else { state = state * UINT32_C(1664525) + UINT32_C(1013904223); a[i] = (int)(state & INT_MAX); }
    }
    double start = now();
    if (sort(a, n, limit, (unsigned)hold)) { free(a); return 1; }
    double elapsed = now() - start;
    for (size_t i = 1; i < n; ++i) if (a[i-1] > a[i]) { fprintf(stderr, "Sort verification failed\n"); free(a); return 1; }
    if (!quiet) { for (size_t i = 0; i < n; ++i) printf("%s%d", i ? " " : "", a[i]); putchar('\n'); }
    fprintf(stderr, "n=%zu threads=%zu seconds=%.6f\n", n, limit, elapsed);
    free(a); return 0;
bad:
    fprintf(stderr, "Usage: %s [--threads 1..256] [--size N] [--pattern random|sorted|reverse] [--seed N] [--quiet] [--hold seconds]\n", argv[0]); return 1;
}
