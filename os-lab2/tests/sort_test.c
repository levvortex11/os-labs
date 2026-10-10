/* Exercise the real sorting functions on arrays checked independently by qsort. */
#define main lab_main
#include "../merge.c"
#undef main

static int compare(const void *a, const void *b) {
    int x = *(const int *)a;
    int y = *(const int *)b;
    return (x > y) - (x < y);
}

int main(void) {
    const int sizes[] = {0, 1, 2, 3, 31, 16383, 16384, 16385, 100003};
    const int limits[] = {1, 2, 3, 4, 8};
    int checks = 0;
    for (size_t s = 0; s < sizeof sizes / sizeof sizes[0]; ++s) {
        int n = sizes[s];
        for (size_t p = 0; p < sizeof limits / sizeof limits[0]; ++p) {
            int *a = calloc((size_t)n + 1, sizeof(int));
            int *expected = calloc((size_t)n + 1, sizeof(int));
            int *buffer = calloc((size_t)n + 1, sizeof(int));
            if (!a || !expected || !buffer) return 1;
            for (int i = 0; i < n; ++i) a[i] = rand() % 201 - 100;
            if (n > 1) { a[0] = INT_MIN; a[1] = INT_MAX; }
            memcpy(expected, a, (size_t)n * sizeof(int));
            qsort(expected, (size_t)n, sizeof(int), compare);
            free_threads = limits[p] - 1;
            ThreadArgs args = {a, buffer, 0, n};
            parallel_sort(&args);
            if (memcmp(a, expected, (size_t)n * sizeof(int)) || free_threads != limits[p] - 1) return 1;
            free(a); free(expected); free(buffer);
            ++checks;
        }
    }
    printf("%d sorting checks passed\n", checks);
    return 0;
}
