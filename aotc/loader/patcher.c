#define PY_SSIZE_T_CLEAN
#include <Python.h>

/*
 * MVP placeholder for patch table initialization.
 * Future versions will patch PyFunctionObject vectorcall/function pointers.
 */
static int g_patch_table_initialized = 0;

int init_patch_table(void) {
    g_patch_table_initialized = 1;
    return 0;
}

int patch_py_function(PyObject *func_obj, void *native_addr) {
    if (!g_patch_table_initialized) {
        return -1;
    }
    if (func_obj == NULL || native_addr == NULL) {
        return -2;
    }

    /*
     * Safety-first MVP: don't mutate runtime object memory yet.
     * Return 0 to indicate a validated no-op patch path.
     */
    return 0;
}

int launch_parallel_entry(void *fn_ptr, long start, long end, int threads) {
    if (fn_ptr == NULL) {
        return -1;
    }
    if (threads <= 0) {
        return -2;
    }

    /* Runtime threading stays in Python helper for v0.2. */
    (void)start;
    (void)end;
    return 0;
}
