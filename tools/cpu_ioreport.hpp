// M1 CPU DRAM counters. IOReport declarations verified against mactop v2.1.6:
// https://github.com/metaspartan/mactop/blob/v2.1.6/internal/app/ioreport.go
// Only the four CPU-cluster DCS byte counters are subscribed, excluding GPU/I/O.
#pragma once

#include <CoreFoundation/CoreFoundation.h>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <map>
#include <ostream>
#include <stdexcept>
#include <string>
#include <sys/sysctl.h>

extern "C" {
struct IOReportSubscriptionRef;
using IOReportSubscription = IOReportSubscriptionRef *;
CFDictionaryRef IOReportCopyChannelsInGroup(CFStringRef, CFStringRef, uint64_t, uint64_t, uint64_t);
IOReportSubscription IOReportCreateSubscription(void *, CFMutableDictionaryRef,
                                               CFMutableDictionaryRef *, uint64_t, CFTypeRef);
CFDictionaryRef IOReportCreateSamples(IOReportSubscription, CFMutableDictionaryRef, CFTypeRef);
CFDictionaryRef IOReportCreateSamplesDelta(CFDictionaryRef, CFDictionaryRef, CFTypeRef);
int64_t IOReportSimpleGetIntegerValue(CFDictionaryRef, int32_t);
CFStringRef IOReportChannelGetChannelName(CFDictionaryRef);
CFStringRef IOReportChannelGetUnitLabel(CFDictionaryRef);
}

class CpuDramCounters {
    using Clock = std::chrono::steady_clock;
    struct Snapshot {
        CFDictionaryRef data = nullptr;
        Clock::time_point before, after;
    } begin_, end_;
    CFMutableDictionaryRef channels_ = nullptr;
    IOReportSubscription subscription_ = nullptr;

    static bool wanted(const std::string & name) {
        return name == "PCPU DCS RD" || name == "PCPU DCS WR" ||
               name == "ECPU DCS RD" || name == "ECPU DCS WR";
    }

    static std::string channel_name(CFDictionaryRef channel) {
        char name[128]{};
        auto value = IOReportChannelGetChannelName(channel);
        if (!value || !CFStringGetCString(value, name, sizeof(name), kCFStringEncodingUTF8))
            throw std::runtime_error("Cannot read IOReport channel name");
        return name;
    }

    static std::map<std::string, int64_t> values(CFDictionaryRef data) {
        if (!data) throw std::runtime_error("No IOReport sample");
        auto array = static_cast<CFArrayRef>(CFDictionaryGetValue(data, CFSTR("IOReportChannels")));
        if (!array) throw std::runtime_error("No IOReport sample channels");
        std::map<std::string, int64_t> out;
        for (CFIndex i = 0; i < CFArrayGetCount(array); ++i) {
            auto channel = static_cast<CFDictionaryRef>(CFArrayGetValueAtIndex(array, i));
            const auto name = channel_name(channel);
            auto unit = IOReportChannelGetUnitLabel(channel);
            if (!wanted(name) || !unit || !CFEqual(unit, CFSTR("B")))
                throw std::runtime_error("Unexpected IOReport channel or unit");
            const auto count = IOReportSimpleGetIntegerValue(channel, 0);
            if (count < 0 || !out.emplace(name, count).second)
                throw std::runtime_error("Invalid or duplicate IOReport counter");
        }
        if (out.size() != 4) throw std::runtime_error("Missing CPU DCS counter");
        return out;
    }

    void sample(Snapshot & out) {
        if (out.data) throw std::runtime_error("IOReport sample already taken");
        out.before = Clock::now();
        out.data = IOReportCreateSamples(subscription_, channels_, nullptr);
        out.after = Clock::now();
        if (!out.data) throw std::runtime_error("IOReport sampling failed");
    }

    static void emit_values(std::ostream & out, const std::map<std::string, int64_t> & rows) {
        out << '{';
        bool first = true;
        for (const auto & row : rows) {
            if (!first) out << ',';
            first = false;
            out << std::quoted(row.first) << ':' << row.second;
        }
        out << '}';
    }

public:
    CpuDramCounters() = default;
    CpuDramCounters(const CpuDramCounters &) = delete;
    CpuDramCounters & operator=(const CpuDramCounters &) = delete;
    ~CpuDramCounters() {
        if (begin_.data) CFRelease(begin_.data);
        if (end_.data) CFRelease(end_.data);
        if (subscription_) CFRelease(subscription_);
        if (channels_) CFRelease(channels_);
    }

    void init() {
        char cpu[128]{};
        size_t length = sizeof(cpu);
        if (sysctlbyname("machdep.cpu.brand_string", cpu, &length, nullptr, 0) ||
            std::strcmp(cpu, "Apple M1") != 0)
            throw std::runtime_error("68.25 GB/s denominator requires base Apple M1");
        auto all = IOReportCopyChannelsInGroup(CFSTR("AMC Stats"), CFSTR("Perf Counters"), 0, 0, 0);
        if (!all) throw std::runtime_error("AMC Stats counters unavailable");
        channels_ = CFDictionaryCreateMutableCopy(kCFAllocatorDefault, 0, all);
        CFRelease(all);
        if (!channels_) throw std::runtime_error("Cannot create channel dictionary");
        auto array = static_cast<CFArrayRef>(CFDictionaryGetValue(channels_, CFSTR("IOReportChannels")));
        if (!array) throw std::runtime_error("No AMC Stats channels");
        auto selected = CFArrayCreateMutable(kCFAllocatorDefault, 0, &kCFTypeArrayCallBacks);
        for (CFIndex i = 0; i < CFArrayGetCount(array); ++i) {
            auto channel = static_cast<CFDictionaryRef>(CFArrayGetValueAtIndex(array, i));
            if (wanted(channel_name(channel))) CFArrayAppendValue(selected, channel);
        }
        const auto count = CFArrayGetCount(selected);
        CFDictionarySetValue(channels_, CFSTR("IOReportChannels"), selected);
        CFRelease(selected);
        // Channel descriptors have no numeric samples until after subscription.
        if (count != 4) throw std::runtime_error("Missing or duplicate CPU DCS descriptor");
        CFMutableDictionaryRef subsystem = nullptr;
        subscription_ = IOReportCreateSubscription(nullptr, channels_, &subsystem, 0, nullptr);
        if (subsystem) CFRelease(subsystem);
        if (!subscription_) throw std::runtime_error("IOReport subscription failed");
    }

    void start() { sample(begin_); }
    void stop() { sample(end_); }

    void write_json(std::ostream & out) const {
        auto delta = IOReportCreateSamplesDelta(begin_.data, end_.data, nullptr);
        std::map<std::string, int64_t> bytes;
        try { bytes = values(delta); }
        catch (...) { if (delta) CFRelease(delta); throw; }
        CFRelease(delta);
        const auto raw_before = values(begin_.data), raw_after = values(end_.data);
        for (const auto & row : bytes)
            if (raw_after.at(row.first) - raw_before.at(row.first) != row.second)
                throw std::runtime_error("IOReport raw and delta counters disagree");
        const auto read = bytes.at("PCPU DCS RD") + bytes.at("ECPU DCS RD");
        const auto write = bytes.at("PCPU DCS WR") + bytes.at("ECPU DCS WR");
        const double lower = std::chrono::duration<double>(end_.before - begin_.after).count();
        const double upper = std::chrono::duration<double>(end_.after - begin_.before).count();
        const double seconds = (lower + upper)/2;
        if (lower <= 0 || read + write <= 0) throw std::runtime_error("Invalid CPU bandwidth interval");
        out << std::setprecision(12)
            << "{\"source\":\"IOReport AMC Stats / Perf Counters\",\"scope\":\"all CPU processes\""
            << ",\"unit\":\"B\",\"read_bytes\":" << read << ",\"write_bytes\":" << write
            << ",\"seconds\":" << seconds << ",\"seconds_lower_bound\":" << lower
            << ",\"seconds_upper_bound\":" << upper << ",\"gb_s\":" << (read + write)/seconds/1e9
            << ",\"gb_s_lower_bound\":" << (read + write)/upper/1e9
            << ",\"gb_s_upper_bound\":" << (read + write)/lower/1e9
            << ",\"peak_gb_s\":68.25,\"percent_of_peak\":" << 100*(read + write)/seconds/68.25e9
            << ",\"channel_bytes\":";
        emit_values(out, bytes);
        out << ",\"raw_before\":";
        emit_values(out, raw_before);
        out << ",\"raw_after\":";
        emit_values(out, raw_after);
        out << '}';
    }
};
