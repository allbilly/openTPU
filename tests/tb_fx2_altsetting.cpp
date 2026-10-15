// SPDX-License-Identifier: Apache-2.0
// Exercise the real FX2 driver against libusb descriptor/transfer responses.
// No USB device is opened: these functions replace only the USB API boundary.
#include <cassert>
#include <cstdint>
#include <iostream>
#include <libusb.h>
#include "fx2_ll.hpp"

namespace {
int descriptor_result = LIBUSB_SUCCESS, selection_result = LIBUSB_SUCCESS;
int selections = 0, frees = 0, selected_interface = -1, selected_alt = -1;
libusb_interface_descriptor alternates[2]{};
libusb_interface interface_desc{};
libusb_config_descriptor config{};
}

extern "C" {
int LIBUSB_CALL libusb_init(libusb_context **ctx) {
    *ctx = reinterpret_cast<libusb_context *>(uintptr_t(1)); return 0;
}
void LIBUSB_CALL libusb_exit(libusb_context *) {}
libusb_device_handle *LIBUSB_CALL libusb_open_device_with_vid_pid(libusb_context *, uint16_t, uint16_t) {
    return reinterpret_cast<libusb_device_handle *>(uintptr_t(2));
}
int LIBUSB_CALL libusb_claim_interface(libusb_device_handle *, int) { return 0; }
int LIBUSB_CALL libusb_release_interface(libusb_device_handle *, int) { return 0; }
void LIBUSB_CALL libusb_close(libusb_device_handle *) {}
libusb_device *LIBUSB_CALL libusb_get_device(libusb_device_handle *) {
    return reinterpret_cast<libusb_device *>(uintptr_t(3));
}
int LIBUSB_CALL libusb_get_active_config_descriptor(libusb_device *, libusb_config_descriptor **out) {
    *out = descriptor_result == LIBUSB_SUCCESS ? &config : nullptr;
    return descriptor_result;
}
void LIBUSB_CALL libusb_free_config_descriptor(libusb_config_descriptor *p) {
    assert(p == &config); ++frees;
}
int LIBUSB_CALL libusb_set_interface_alt_setting(libusb_device_handle *, int number, int alt) {
    ++selections; selected_interface = number; selected_alt = alt;
    return selection_result;
}
}

int main() {
    config.bNumInterfaces = 1;
    config.interface = &interface_desc;
    interface_desc.altsetting = alternates;
    interface_desc.num_altsetting = 1;
    alternates[0].bInterfaceNumber = 0;
    alternates[0].bAlternateSetting = 0;
    alternates[1].bInterfaceNumber = 0;
    alternates[1].bAlternateSetting = 1;
    FX2_ll driver(0, 0, 0x03fd, 0x0008, "", 0);

    // Alt-0-only firmware: do not issue an invalid SET_INTERFACE request.
    assert(driver.set_interface_alt_setting(0, 1));
    assert(selections == 0 && frees == 1);

    // Firmware advertising alt 1 must still receive the selection request.
    interface_desc.num_altsetting = 2;
    assert(driver.set_interface_alt_setting(0, 1));
    assert(selections == 1 && frees == 2 && selected_interface == 0 && selected_alt == 1);

    // Advertised selection failures remain failures.
    selection_result = LIBUSB_ERROR_ACCESS;
    assert(!driver.set_interface_alt_setting(0, 1));
    assert(selections == 2 && frees == 3);

    // Descriptor-read failures preserve the original driver's fallback.
    descriptor_result = LIBUSB_ERROR_IO;
    selection_result = LIBUSB_SUCCESS;
    assert(driver.set_interface_alt_setting(0, 1));
    assert(selections == 3 && frees == 3);
    selection_result = LIBUSB_ERROR_NO_DEVICE;
    assert(!driver.set_interface_alt_setting(0, 1));
    assert(selections == 4 && frees == 3);
    std::cout << "PASS: absent alternate skipped, present alternate selected, USB failures retained\n";
}
