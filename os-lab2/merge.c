#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdint.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

/* No stdio, malloc, string conversion or random library functions. */
static void write_text(int fd, const char *text) {
    size_t length = 0;
    while (text[length]) ++length;
    while (length > 0) {
        ssize_t done = write(fd, text, length);
        if (done < 0 && errno == EINTR) continue;
        if (done <= 0) _exit(1);
        text += done;
        length -= (size_t)done;
    }
}

static void print_int(int fd, long long value) {
    char text[32];
    int position = 31;
    text[position] = '\0';
    uint64_t number = value < 0 ? 0 - (uint64_t)value : (uint64_t)value;
    do {
        text[--position] = (char)('0' + number % 10);
        number /= 10;
    } while (number);
    if (value < 0) text[--position] = '-';
    write_text(fd, text + position);
}

static void print_value(const char *name, double value) {
    /* All measured values are nonnegative. Print six fractional digits. */
    uint64_t scaled = (uint64_t)(value * 1000000.0 + 0.5);
    write_text(1, name);
    print_int(1, (long long)(scaled / 1000000));
    write_text(1, ".");
    uint64_t fraction = scaled % 1000000;
    char digits[7];
    digits[6] = '\0';
    for (int i = 5; i >= 0; --i) {
        digits[i] = (char)('0' + fraction % 10);
        fraction /= 10;
    }
    write_text(1, digits);
    write_text(1, "\n");
}

static void fail(const char *message) {
    write_text(2, message);
    write_text(2, "\n");
    _exit(1);
}

static int equal(const char *a, const char *b) {
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}

/* The main thread also counts towards the limit. */
static int threads_left;
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;

typedef struct {
    int *array;
    int *buffer;
    int left;
    int right;
} ThreadArgs;

static void check_thread(int error) {
    if (error != 0) {
        write_text(2, "pthread error: ");
        print_int(2, error);
        fail("");
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
    int can_create = threads_left > 0;
    if (can_create) --threads_left;
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

    /* Do not reuse slots: at most P threads are created in the whole run. */
    merge(args->array, args->buffer, left, middle, right);
}

static int read_number(const char *text, int maximum) {
    if (!*text) fail("Expected a positive integer");
    int value = 0;
    for (int i = 0; text[i]; ++i) {
        if (text[i] < '0' || text[i] > '9') fail("Expected decimal digits");
        int digit = text[i] - '0';
        if (value > maximum / 10 ||
            (value == maximum / 10 && digit > maximum % 10)) {
            fail("Number exceeds the limit");
        }
        value = value * 10 + digit;
    }
    if (value == 0) fail("Expected a positive integer");
    return value;
}

/* Read one signed int from stdin, separated by whitespace. */
static int read_int(void) {
    uint64_t value = 0;
    int negative = 0, started = 0, digits = 0;
    for (;;) {
        char c;
        ssize_t count = read(0, &c, 1);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) fail("Input read failed");
        if (count == 0) {
            if (!digits) fail("Not enough integers");
            break;
        }
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f') {
            if (!started) continue;
            if (!digits) fail("Expected digits after sign");
            break;
        }
        if (!started && (c == '-' || c == '+')) {
            negative = c == '-';
            started = 1;
            continue;
        }
        if (c < '0' || c > '9') fail("Invalid integer");
        uint64_t limit = (uint64_t)INT_MAX + (uint64_t)negative;
        uint64_t digit = (uint64_t)(c - '0');
        if (value > (limit - digit) / 10) fail("Integer outside int range");
        value = value * 10 + digit;
        started = 1;
        digits = 1;
    }
    if (negative && value == (uint64_t)INT_MAX + 1) return INT_MIN;
    return negative ? -(int)value : (int)value;
}

static double get_time(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) {
        fail("clock_gettime failed");
    }
    return (double)t.tv_sec + (double)t.tv_nsec / 1000000000.0;
}

static void print_array(const char *name, const int *array, int n) {
    write_text(1, name);
    write_text(1, ":");
    for (int i = 0; i < n; ++i) {
        write_text(1, " ");
        print_int(1, array[i]);
    }
    write_text(1, "\n");
}

int main(int argc, char **argv) {
    if (argc < 2 || argc > 4) {
        fail("Usage: ./merge THREADS [SIZE] [random|sorted|reverse|manual]");
    }
    int threads = read_number(argv[1], 4096);
    int n = argc >= 3 ? read_number(argv[2], INT_MAX) : 5000000;
    const char *pattern = argc == 4 ? argv[3] : "random";
    int manual = equal(pattern, "manual");
    if (!equal(pattern, "random") && !equal(pattern, "sorted") && !equal(pattern, "reverse") && !manual) {
        fail("Unknown pattern");
    }

    if ((size_t)n > SIZE_MAX / sizeof(int) / 3) fail("Array too large");
    size_t bytes = (size_t)n * 3 * sizeof(int);
    int *memory = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (memory == MAP_FAILED) fail("mmap failed");
    int *sequential = memory;
    int *parallel = memory + n;
    int *buffer = parallel + n;

    if (manual) {
        write_text(1, "Enter ");
        print_int(1, n);
        write_text(1, " integers separated by spaces or newlines:\n");
    }
    uint32_t state = 42;
    for (int i = 0; i < n; ++i) {
        if (manual) sequential[i] = read_int();
        else if (equal(pattern, "sorted")) sequential[i] = i;
        else if (equal(pattern, "reverse")) sequential[i] = n - i;
        else {
            state = state * UINT32_C(1664525) + UINT32_C(1013904223);
            sequential[i] = (int)(state % 100000);
        }
        parallel[i] = sequential[i];
    }
    if (n <= 20) print_array("Before", parallel, n);

    double start = get_time();
    merge_sort(sequential, buffer, 0, n);
    double sequential_time = get_time() - start;

    threads_left = threads - 1;
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
    write_text(1, "Elements: "); print_int(1, n);
    write_text(1, "\nThreads limit: "); print_int(1, threads);
    write_text(1, "\nThreads created incl main: "); print_int(1, threads - threads_left);
    write_text(1, "\nLogical CPUs: "); print_int(1, sysconf(_SC_NPROCESSORS_ONLN));
    write_text(1, "\n");
    print_value("Sequential ms: ", sequential_time * 1000);
    print_value("Parallel ms: ", parallel_time * 1000);
    print_value("Speedup: ", speedup);
    print_value("Efficiency: ", speedup / threads);
    write_text(1, valid ? "Check: OK\n" : "Check: FAILED\n");

    if (munmap(memory, bytes) != 0) fail("munmap failed");
    return valid ? 0 : 1;
}
