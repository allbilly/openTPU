// Native CPU timing for the same token workload as chestnut_benchmark.py.
// Built against the installed llama.cpp C API; no GPU backend is registered.
#include "llama.h"
#include "ggml-backend.h"
#include "cpu_ioreport.hpp"

#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

using Clock = std::chrono::steady_clock;

static std::vector<llama_token> read_tokens(const char * path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot open token file");
    std::vector<llama_token> tokens;
    llama_token token;
    while (input >> token) tokens.push_back(token);
    if (!input.eof() || tokens.empty()) throw std::runtime_error("Invalid token file");
    return tokens;
}

static void emit_tokens(const std::vector<llama_token> & tokens) {
    std::cout << '[';
    for (size_t i = 0; i < tokens.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << tokens[i];
    }
    std::cout << ']';
}

int main(int argc, char ** argv) {
    try {
        if (argc != 8 && argc != 9) throw std::runtime_error(
            "Usage: cpu_benchmark MODEL PROMPT_IDS CHAT_IDS THREADS STEPS CPU_BACKEND BLAS_BACKEND [MEASURE_BW_0_OR_1]");
        const bool measure_bw = argc == 9 && std::string(argv[8]) == "1";
        if (argc == 9 && !measure_bw && std::string(argv[8]) != "0")
            throw std::runtime_error("Bandwidth argument must be 0 or 1");
        const auto prompt = read_tokens(argv[2]);
        const auto chat = read_tokens(argv[3]);
        const int threads = std::stoi(argv[4]), steps = std::stoi(argv[5]);
        if (prompt.size() != 512 || steps != 64 || threads < 1 || chat.size() + 16 > 1024)
            throw std::runtime_error("Expected 512 prompt tokens, 64 decode steps and positive threads");
        if (!ggml_backend_load(argv[6]) || !ggml_backend_load(argv[7]))
            throw std::runtime_error("Cannot load CPU/BLAS backends");
        for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
            auto dev = ggml_backend_dev_get(i);
            if (ggml_backend_dev_type(dev) == GGML_BACKEND_DEVICE_TYPE_GPU)
                throw std::runtime_error("GPU backend unexpectedly registered");
            std::cerr << "CPU_DEVICE " << ggml_backend_dev_name(dev) << '\n';
        }
        llama_backend_init();
        ggml_backend_dev_t no_devices[] = {nullptr};
        auto mp = llama_model_default_params();
        mp.devices = no_devices;
        mp.n_gpu_layers = 0;
        mp.load_mode = LLAMA_LOAD_MODE_MMAP;
        std::unique_ptr<llama_model, decltype(&llama_model_free)> model(
            llama_model_load_from_file(argv[1], mp), llama_model_free);
        if (!model) throw std::runtime_error("Model load failed");
        auto cp = llama_context_default_params();
        cp.n_ctx = 1024;
        cp.n_batch = 512;
        cp.n_ubatch = 512;
        cp.n_seq_max = 1;
        cp.n_threads = threads;
        cp.n_threads_batch = threads;
        cp.offload_kqv = false;
        cp.op_offload = false;
        std::unique_ptr<llama_context, decltype(&llama_free)> ctx(
            llama_init_from_model(model.get(), cp), llama_free);
        if (!ctx) throw std::runtime_error("Context creation failed");
        const int vocab = llama_vocab_n_tokens(llama_model_get_vocab(model.get()));
        for (const auto * tokens : {&prompt, &chat})
            for (auto token : *tokens)
                if (token < 0 || token >= vocab) throw std::runtime_error("Token outside vocabulary");

        auto process = [&](const std::vector<llama_token> & tokens, int start) {
            std::vector<llama_pos> positions(tokens.size());
            for (size_t i = 0; i < tokens.size(); ++i) positions[i] = start + i;
            llama_batch batch{};
            batch.n_tokens = tokens.size();
            batch.token = const_cast<llama_token *>(tokens.data());
            batch.pos = positions.data();
            if (llama_decode(ctx.get(), batch) != 0) throw std::runtime_error("llama_decode failed");
            llama_synchronize(ctx.get());
        };
        auto argmax = [&]() {
            const float * logits = llama_get_logits_ith(ctx.get(), -1);
            if (!logits) throw std::runtime_error("Missing logits");
            llama_token best = 0;
            for (int i = 0; i < vocab; ++i) {
                if (!std::isfinite(logits[i])) throw std::runtime_error("Nonfinite logits");
                if (logits[i] > logits[best]) best = i;
            }
            return best;
        };
        auto clear = [&]() { llama_memory_clear(llama_get_memory(ctx.get()), true); };
        CpuDramCounters dram;
        if (measure_bw) dram.init();

        // Untimed chat sanity check also exercises one-token execution.
        process(chat, 0);
        std::vector<llama_token> chat_output{argmax()};
        for (int i = 1; i < 16; ++i) {
            process({chat_output.back()}, chat.size() + i - 1);
            chat_output.push_back(argmax());
        }
        clear();
        // Warm the full prefill graph, weights and single-token decode graph.
        process(prompt, 0);
        process({argmax()}, prompt.size());
        (void) argmax();
        clear();

        std::cerr << "TIMED_PREFILL\n";
        auto begin = Clock::now();
        process(prompt, 0);
        const double prefill = std::chrono::duration<double>(Clock::now() - begin).count();
        llama_token token = argmax();
        const llama_token first = token;
        std::vector<llama_token> decoded;
        decoded.reserve(steps);
        std::cerr << "TIMED_DECODE\n";
        if (measure_bw) dram.start();
        begin = Clock::now();
        for (int i = 0; i < steps; ++i) {
            process({token}, prompt.size() + i);
            token = argmax();
            decoded.push_back(token);
        }
        const double decode = std::chrono::duration<double>(Clock::now() - begin).count();
        if (measure_bw) dram.stop();
        std::cout << std::setprecision(12)
                  << "{\"status\":\"PASS_NATIVE_CPU_BENCHMARK\",\"runtime_version\":"
                  << std::quoted(llama_version()) << ",\"gpu_layers\":0,\"gpu_backend_registered\":false"
                  << ",\"threads\":" << llama_n_threads(ctx.get())
                  << ",\"batch_threads\":" << llama_n_threads_batch(ctx.get())
                  << ",\"context\":1024,\"batch\":512,\"ubatch\":512,\"repetitions\":1"
                  << ",\"model_bytes\":" << llama_model_size(model.get())
                  << ",\"model_parameters\":" << llama_model_n_params(model.get())
                  << ",\"prefill\":{\"tokens\":512,\"wall_seconds\":" << prefill
                  << ",\"wall_tok_s\":" << 512 / prefill << '}'
                  << ",\"decode\":{\"steps\":" << steps << ",\"wall_seconds\":" << decode
                  << ",\"wall_tok_s\":" << steps / decode << ",\"first_token_id\":" << first
                  << ",\"token_ids\":";
        emit_tokens(decoded);
        if (measure_bw) {
            std::cout << ",\"dram_bandwidth\":";
            dram.write_json(std::cout);
        }
        std::cout << "},\"chat_token_ids\":";
        emit_tokens(chat_output);
        std::cout << "}\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "CPU_BENCHMARK_ERROR " << error.what() << '\n';
        return 1;
    }
}
