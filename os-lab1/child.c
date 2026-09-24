#define _POSIX_C_SOURCE 200809L
#include "common.h"
#include <fcntl.h>
#include <limits.h>

struct parser {
    int result;
    int has_result;
    int token;
    int negative;
    int digits;
    int line_started;
    unsigned int magnitude;
};

static int finish_number(struct parser *p)
{
    if (!p->token) return 0;
    if (!p->digits) { message("A sign must be followed by digits.\n"); return -1; }
    int value;
    if (p->negative && p->magnitude == (unsigned int)INT_MAX + 1U)
        value = INT_MIN;
    else
        value = p->negative ? -(int)p->magnitude : (int)p->magnitude;
    if (!p->has_result) {
        p->result = value;
        p->has_result = 1;
    } else {
        if (value == 0) { message("Division by zero.\n"); return -1; }
        if (p->result == INT_MIN && value == -1) {
            message("Integer division overflow.\n"); return -1;
        }
        p->result /= value;
    }
    p->token = p->negative = p->digits = 0;
    p->magnitude = 0;
    return 0;
}

static int finish_line(struct parser *p, int file)
{
    if (finish_number(p) < 0) return -1;
    if (!p->has_result) { message("Empty command.\n"); return -1; }
    char reversed[sizeof(int) * CHAR_BIT + 2];
    char output[sizeof(reversed)];
    size_t n = 0, used = 0;
    unsigned int value = p->result < 0 ?
        0U - (unsigned int)p->result : (unsigned int)p->result;
    do {
        reversed[n++] = (char)('0' + value % 10U);
        value /= 10U;
    } while (value != 0);
    if (p->result < 0) output[used++] = '-';
    while (n != 0) output[used++] = reversed[--n];
    output[used++] = '\n';
    if (write_all(file, output, used) < 0) { system_error("write file"); return -1; }
    *p = (struct parser){0};
    return 0;
}

static int consume(struct parser *p, unsigned char c, int file)
{
    if (c == '\n') return finish_line(p, file);
    p->line_started = 1;
    if (c == ' ' || c == '\t' || c == '\r' || c == '\v' || c == '\f')
        return finish_number(p);
    if (!p->token) {
        p->token = 1;
        if (c == '+' || c == '-') { p->negative = c == '-'; return 0; }
    }
    if (c < '0' || c > '9') { message("Invalid integer.\n"); return -1; }
    unsigned int digit = (unsigned int)(c - '0');
    unsigned int limit = (unsigned int)INT_MAX + (p->negative ? 1U : 0U);
    if (p->magnitude > (limit - digit) / 10U) {
        message("Integer is out of range.\n"); return -1;
    }
    p->magnitude = p->magnitude * 10U + digit;
    p->digits = 1;
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 2) { message("Usage: child output-file\n"); return 1; }
    int file = open(argv[1], O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (file < 0) {
        system_error("open output file");
        (void)write_all(STDOUT_FILENO, "E", 1);
        return 1;
    }
    struct parser parser = {0};
    int failed = 0;
    while (!failed) {
        char buffer[4096];
        ssize_t n = read(STDIN_FILENO, buffer, sizeof(buffer));
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) { system_error("read pipe1"); failed = 1; break; }
        if (n == 0) {
            if (parser.line_started && finish_line(&parser, file) < 0) failed = 1;
            break;
        }
        for (ssize_t i = 0; i < n; ++i) {
            if (consume(&parser, (unsigned char)buffer[i], file) < 0) {
                failed = 1; break;
            }
        }
    }
    if (close_checked(file) < 0) failed = 1;
    if (failed && write_all(STDOUT_FILENO, "E", 1) < 0) system_error("write pipe2");
    return failed ? 1 : 0;
}
