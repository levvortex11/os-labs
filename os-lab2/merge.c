#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* The main thread also counts towards the limit. */
static int free_threads;
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;

typedef struct {
    int *array;
    int *buffer;
    int left;
    int right;
} ThreadArgs;

static void check_thread(int error) {
    if (error != 0) {
        fprintf(stderr, "pthread: %s\n", strerror(error));
        exit(EXIT_FAILURE);
    }
}

/* Merge the sorted ranges [left, middle) and [middle, right). */
static void merge(int *array, int *buffer, int left, int middle, int right) {
    int i = left;
    int j = middle;
    int k = left;

    while (i < middle && j < right) {
        if (array[i] <= array[j]) {
            buffer[k++] = array[i++];
        } else {
            buffer[k++] = array[j++];
        }
    }
    while (i < middle) buffer[k++] = array[i++];
    while (j < right) buffer[k++] = array[j++];
    for (k = left; k < right; ++k) array[k] = buffer[k];
}

static void merge_sort(int *array, int *buffer, int left, int right) {
    if (right - left < 2) return;
    int middle = left + (right - left) / 2;
    merge_sort(array, buffer, left, middle);
    merge_sort(array, buffer, middle, right);
    merge(array, buffer, left, middle, right);
}

static void parallel_sort(ThreadArgs *args);

static void *sort_thread(void *data) {
    parallel_sort(data);
    return NULL;
}

static void parallel_sort(ThreadArgs *args) {
    int left = args->left;
    int right = args->right;

    /* Small ranges are cheaper to sort without creating threads. */
    if (right - left < 16384) {
        merge_sort(args->array, args->buffer, left, right);
        return;
    }

    check_thread(pthread_mutex_lock(&mutex));
    int can_create = free_threads > 0;
    if (can_create) --free_threads;
    check_thread(pthread_mutex_unlock(&mutex));

    if (!can_create) {
        merge_sort(args->array, args->buffer, left, right);
        return;
    }

    int middle = left + (right - left) / 2;
    ThreadArgs first = {args->array, args->buffer, left, middle};
    ThreadArgs second = {args->array, args->buffer, middle, right};
    pthread_t thread;

    check_thread(pthread_create(&thread, NULL, sort_thread, &first));
    parallel_sort(&second);
    check_thread(pthread_join(thread, NULL));

    /* Release the slot only after the child has finished. */
    check_thread(pthread_mutex_lock(&mutex));
    ++free_threads;
    check_thread(pthread_mutex_unlock(&mutex));

    merge(args->array, args->buffer, left, middle, right);
}

static int read_number(const char *text, int maximum) {
    char *end;
    errno = 0;
    long value = strtol(text, &end, 10);
    if (errno || end == text || *end != '\0' || value < 1 || value > maximum) {
        fprintf(stderr, "Invalid number: %s\n", text);
        exit(EXIT_FAILURE);
    }
    return (int)value;
}

static double get_time(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) {
        perror("clock_gettime");
        exit(EXIT_FAILURE);
    }
    return (double)t.tv_sec + (double)t.tv_nsec / 1000000000.0;
}

static void print_array(const char *name, const int *array, int n) {
    printf("%s:", name);
    for (int i = 0; i < n; ++i) printf(" %d", array[i]);
    putchar('\n');
}

int main(int argc, char **argv) {
    if (argc < 2 || argc > 4) {
        fprintf(stderr, "Usage: %s THREADS [SIZE] [random|sorted|reverse]\n", argv[0]);
        return EXIT_FAILURE;
    }
    int threads = read_number(argv[1], 256);
    int n = argc >= 3 ? read_number(argv[2], INT_MAX) : 5000000;
    const char *pattern = argc == 4 ? argv[3] : "random";
    if (strcmp(pattern, "random") && strcmp(pattern, "sorted") && strcmp(pattern, "reverse")) {
        fprintf(stderr, "Unknown pattern: %s\n", pattern);
        return EXIT_FAILURE;
    }

    int *sequential = calloc((size_t)n, sizeof(int));
    int *parallel = calloc((size_t)n, sizeof(int));
    int *buffer = calloc((size_t)n, sizeof(int));
    if (!sequential || !parallel || !buffer) {
        fprintf(stderr, "Not enough memory\n");
        free(sequential);
        free(parallel);
        free(buffer);
        return EXIT_FAILURE;
    }

    srand(42);
    for (int i = 0; i < n; ++i) {
        if (!strcmp(pattern, "sorted")) sequential[i] = i;
        else if (!strcmp(pattern, "reverse")) sequential[i] = n - i;
        else sequential[i] = rand() % 100000;
        parallel[i] = sequential[i];
    }
    if (n <= 20) print_array("Before", parallel, n);

    double start = get_time();
    merge_sort(sequential, buffer, 0, n);
    double sequential_time = get_time() - start;

    free_threads = threads - 1;
    ThreadArgs args = {parallel, buffer, 0, n};
    start = get_time();
    parallel_sort(&args);
    double parallel_time = get_time() - start;

    int valid = 1;
    for (int i = 0; i < n; ++i) {
        if (parallel[i] != sequential[i]) valid = 0;
        if (i > 0 && parallel[i - 1] > parallel[i]) valid = 0;
    }
    if (n <= 20) print_array("After", parallel, n);
    double speedup = parallel_time > 0 ? sequential_time / parallel_time : 0;
    printf("Elements: %d\nThreads limit: %d\n", n, threads);
    printf("Sequential time: %.9f s\nParallel time: %.9f s\n", sequential_time, parallel_time);
    printf("Speedup: %.3f\nEfficiency: %.3f\n", speedup, speedup / threads);
    printf("Check: %s\n", valid ? "OK" : "FAILED");

    free(sequential);
    free(parallel);
    free(buffer);
    return valid ? EXIT_SUCCESS : EXIT_FAILURE;
}
