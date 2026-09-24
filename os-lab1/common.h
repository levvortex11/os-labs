#ifndef LAB_COMMON_H
#define LAB_COMMON_H

#include <errno.h>
#include <stddef.h>
#include <unistd.h>

/* No stdio or string conversion functions are used. */
static size_t text_length(const char *s)
{
    size_t n = 0;
    while (s[n] != '\0') ++n;
    return n;
}

static int write_all(int fd, const char *data, size_t size)
{
    while (size != 0) {
        ssize_t n = write(fd, data, size);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        data += n;
        size -= (size_t)n;
    }
    return 0;
}

static void message(const char *s)
{
    /* A diagnostic failure cannot itself be reported reliably. */
    (void)write_all(STDERR_FILENO, s, text_length(s));
}

static void system_error(const char *operation)
{
    unsigned int code = (unsigned int)errno;
    char digits[16];
    size_t n = 0;
    do {
        digits[n++] = (char)('0' + code % 10U);
        code /= 10U;
    } while (code != 0);
    message(operation);
    message(": errno=");
    while (n != 0) (void)write_all(STDERR_FILENO, &digits[--n], 1);
    message("\n");
}

/* On Linux, do not retry close after EINTR: the fd may already be closed. */
static int close_checked(int fd)
{
    if (close(fd) == 0) return 0;
    system_error("close");
    return -1;
}

#endif
