// SPDX-License-Identifier: Apache-2.0
// Aligned, single-word MMIO. Use an uncached resource0 mapping, never resource0_wc.
#include <stdint.h>
#include <stdatomic.h>
#include <endian.h>

uint32_t otpu_mmio_read32(volatile uint32_t *base, uint32_t offset) {
    atomic_thread_fence(memory_order_seq_cst);
    uint32_t value = base[offset / 4];
    atomic_thread_fence(memory_order_seq_cst);
    return le32toh(value);
}

void otpu_mmio_write32(volatile uint32_t *base, uint32_t offset, uint32_t value) {
    atomic_thread_fence(memory_order_seq_cst);
    base[offset / 4] = htole32(value);
    atomic_thread_fence(memory_order_seq_cst);
}
