// SPDX-License-Identifier: GPL-3.0-or-later
#include "builder.hpp"
#include <chrono>
#include <iostream>
#include <portable-file-dialogs.h>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#endif

namespace {
constexpr const char *title = "The Secret of Monkey Island: Amiga Talkie Edition";
struct Cancelled {};
std::string ask(const std::string &label) {
    std::cout << label << "\n> " << std::flush;
    std::string value;
    if (!std::getline(std::cin, value) || value.empty())
        throw Cancelled{};
    if (value.size() > 1 && value.front() == '"' && value.back() == '"')
        value = value.substr(1, value.size() - 2);
    return value;
}
std::string folder(const std::string &label, bool gui) {
    auto v = gui ? pfd::select_folder(label).result() : ask(label);
    if (v.empty())
        throw Cancelled{};
    return v;
}
std::string file(const std::string &label, const std::vector<std::string> &filter, bool gui) {
    if (!gui)
        return ask(label);
    auto v = pfd::open_file(label, "", filter).result();
    if (v.empty())
        throw Cancelled{};
    return v.front();
}
int run(const std::vector<std::string> &args) {
    using namespace talkie;
    bool interactive = args.empty(), gui = false;
    try {
        std::cout << title << "\nNative Amiga game builder\n\n";
        if (args == std::vector<std::string>{"--help"}) {
            std::cout << "Double-click or run without arguments to choose your local files.\n\n"
                         "--amiga <folder> --sou <monster.sou> --engine <Monkey_Island or "
                         "disk1.adf> --output <new-folder>\n"
                         "--verify-payload   Verify embedded patch and runtime "
                         "hashes.\n--self-test        Verify embedded data and binary format test "
                         "vectors.\n";
            return 0;
        }
        verify_payload();
        if (args == std::vector<std::string>{"--verify-payload"}) {
            std::cout << "Embedded payload checksums OK.\n";
            return 0;
        }
        if (args == std::vector<std::string>{"--self-test"}) {
            self_test();
            std::cout << "Format and checksum tests OK.\n";
            return 0;
        }
        Options options;
        if (interactive) {
            gui = pfd::settings::available();
            auto amiga = folder("Select your English Amiga Monkey Island data folder (000.LFL, "
                                "disk01.lec, music.dat)",
                                gui);
            auto sou = file("Select your Ultimate Talkie monster.sou",
                            {"Speech archive", "monster.sou", "All files", "*"}, gui);
            fs::path engine = fs::u8path(amiga) / "Monkey_Island";
            if (!fs::is_regular_file(engine))
                engine = fs::u8path(file(
                    "Select the ORIGINAL Monkey_Island executable or original disk 1 ADF",
                    {"Amiga executable or disk image", "Monkey_Island *.adf", "All files", "*"},
                    gui));
            auto parent = folder("Choose where to create the finished Amiga game folder", gui);
            fs::path output = fs::u8path(parent) / "Monkey_Island_Amiga_Talkie";
            if (fs::exists(output))
                output += fs::u8path(
                    "-" +
                    std::to_string(std::chrono::system_clock::now().time_since_epoch().count()));
            options = {fs::u8path(amiga), fs::u8path(sou), engine, output};
        } else {
            std::map<std::string, std::string> flags;
            for (std::size_t i = 0; i < args.size(); i += 2) {
                if (i + 1 >= args.size() ||
                    (args[i] != "--amiga" && args[i] != "--sou" && args[i] != "--engine" &&
                     args[i] != "--output") ||
                    !flags.emplace(args[i], args[i + 1]).second)
                    throw std::runtime_error("Use --help for the four required options.");
            }
            if (flags.size() != 4)
                throw std::runtime_error(
                    "Supply --amiga, --sou, --engine and --output, or run without arguments.");
            options = {fs::u8path(flags.at("--amiga")), fs::u8path(flags.at("--sou")),
                       fs::u8path(flags.at("--engine")), fs::u8path(flags.at("--output"))};
        }
        auto summary =
            build(options, [](const std::string &message) { std::cout << message << std::endl; });
        std::cout << "\n" << summary << std::endl;
        if (gui)
            pfd::message(title, summary, pfd::choice::ok, pfd::icon::info).result();
        return 0;
    } catch (const Cancelled &) {
        std::cout << "Cancelled. No build was started.\n";
        return 2;
    } catch (const std::exception &error) {
        std::string message = std::string("Build failed: ") + error.what() +
                              "\nYour original game files were not modified.";
        std::cerr << message << std::endl;
        if (gui)
            pfd::message(title, message, pfd::choice::ok, pfd::icon::error).result();
        return 1;
    }
}
} // namespace
#ifdef _WIN32
int wmain(int argc, wchar_t **argv) {
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
    std::vector<std::string> args;
    for (int i = 1; i < argc; ++i) {
        int n = WideCharToMultiByte(CP_UTF8, 0, argv[i], -1, nullptr, 0, nullptr, nullptr);
        std::string value(static_cast<std::size_t>(n), '\0');
        WideCharToMultiByte(CP_UTF8, 0, argv[i], -1, value.data(), n, nullptr, nullptr);
        value.pop_back();
        args.push_back(value);
    }
    return run(args);
}
#else
int main(int argc, char **argv) {
    return run(std::vector<std::string>(argv + 1, argv + argc));
}
#endif
