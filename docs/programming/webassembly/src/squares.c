// squares.c: one C function, and one function it borrows from the page
__attribute__((import_module("env"), import_name("show")))
void show(int n);                 /* written in JavaScript, given to the module */

__attribute__((export_name("sum_squares")))
int sum_squares(int n) {          /* 1*1 + 2*2 + ... + n*n */
    int total = 0;
    for (int i = 1; i <= n; i++)
        total += i * i;
    show(total);
    return total;
}
