#define _POSIX_C_SOURCE 200809L
#include "common.h"
#include <poll.h>
#include <signal.h>
#include <sys/wait.h>

static int read_filename(char *name, size_t capacity)
{
    size_t used = 0;
    for (;;) {
        char c;
        ssize_t n = read(STDIN_FILENO, &c, 1);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) { system_error("read filename"); return -1; }
        if (n == 0 || c == '\n') break;
        if (c == '\0' || used + 1 >= capacity) {
            message("Invalid or too long filename.\n");
            return -1;
        }
        name[used++] = c;
    }
    if (used != 0 && name[used - 1] == '\r') --used;
    name[used] = '\0';
    if (used == 0) { message("Filename is required.\n"); return -1; }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc > 2) { message("Usage: ./parent [path-to-child]\n"); return 1; }
    char filename[4096];
    if (read_filename(filename, sizeof(filename)) < 0) return 1;

    struct sigaction action = {0};
    action.sa_handler = SIG_IGN;
    if (sigemptyset(&action.sa_mask) < 0 ||
        sigaction(SIGPIPE, &action, NULL) < 0) {
        system_error("sigaction"); return 1;
    }
    int commands[2], status_pipe[2];
    if (pipe(commands) < 0) { system_error("pipe1"); return 1; }
    if (pipe(status_pipe) < 0) {
        system_error("pipe2");
        close_checked(commands[0]); close_checked(commands[1]);
        return 1;
    }
    pid_t child = fork();
    if (child < 0) {
        system_error("fork");
        close_checked(commands[0]); close_checked(commands[1]);
        close_checked(status_pipe[0]); close_checked(status_pipe[1]);
        return 1;
    }
    if (child == 0) {
        if (close_checked(commands[1]) < 0 ||
            close_checked(status_pipe[0]) < 0) _exit(1);
        if (dup2(commands[0], STDIN_FILENO) < 0 ||
            dup2(status_pipe[1], STDOUT_FILENO) < 0) {
            system_error("dup2"); _exit(1);
        }
        if (close_checked(commands[0]) < 0 ||
            close_checked(status_pipe[1]) < 0) _exit(1);
        char *path = argc == 2 ? argv[1] : "./child";
        char *args[] = {path, filename, NULL};
        execv(path, args);
        system_error("execv");
        _exit(1);
    }

    int failed = 0;
    if (close_checked(commands[0]) < 0) failed = 1;
    if (close_checked(status_pipe[1]) < 0) failed = 1;
    struct pollfd fds[2] = {
        {STDIN_FILENO, POLLIN, 0}, {status_pipe[0], POLLIN, 0}
    };
    int input_open = 1;
    while (!failed) {
        int ready = poll(fds, 2, -1);
        if (ready < 0 && errno == EINTR) continue;
        if (ready < 0) { system_error("poll"); failed = 1; break; }
        /* Read child status first, even if the terminal is still open. */
        if (fds[1].revents & (POLLIN | POLLHUP | POLLERR)) {
            char code;
            ssize_t n = read(status_pipe[0], &code, 1);
            if (n < 0 && errno == EINTR) continue;
            if (n < 0) { system_error("read pipe2"); failed = 1; }
            if (n > 0) failed = 1; /* Child sends 'E' on an error. */
            break; /* EOF also means the child has finished. */
        }
        if ((fds[0].revents | fds[1].revents) & POLLNVAL) {
            message("poll: invalid descriptor.\n"); failed = 1; break;
        }
        if (fds[0].revents & (POLLIN | POLLHUP | POLLERR)) {
            char buffer[4096];
            ssize_t n = read(STDIN_FILENO, buffer, sizeof(buffer));
            if (n < 0 && errno == EINTR) continue;
            if (n < 0) { system_error("read stdin"); failed = 1; break; }
            if (n == 0) {
                if (close_checked(commands[1]) < 0) failed = 1;
                input_open = 0;
                fds[0].fd = -1;
            } else if (write_all(commands[1], buffer, (size_t)n) < 0) {
                system_error("write pipe1"); failed = 1;
            }
        }
    }
    if (input_open && close_checked(commands[1]) < 0) failed = 1;
    if (close_checked(status_pipe[0]) < 0) failed = 1;
    int status;
    pid_t waited;
    do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
    if (waited < 0) { system_error("waitpid"); return 1; }
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) failed = 1;
    return failed ? 1 : 0;
}
