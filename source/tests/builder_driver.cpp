#include "builder.hpp"
#include "staging.hpp"
#include <chrono>
#include <iostream>
#include <thread>

// Paths are relative to the test's working directory, so narrow argv is portable.
int main(int argc, char **argv) {
    using namespace talkie;
    try {
        if (argc != 2)
            return 2;
        std::string mode = argv[1];
        if (mode == "pcm") {
            auto spec = Json::parse(read_file("spec.json"));
            Map map{unhex(spec["map"].get<std::string>()), {}, 0, 0};
            for (const auto &ref : spec["refs"])
                map.references.push_back(
                    {ref[0].get<std::uint32_t>(), ref[1].get<std::uint32_t>()});
            prepare_pcm("archive.sou", map, "voice.pcm", spec["expected"].get<std::string>());
        } else {
            auto output = fs::current_path() / "game";
            StagingDirectory staging(output, mode == "keep");
            write_file(staging.path() / "partial", Bytes{1, 2, 3});
            if (mode == "hold") {
                std::cout << "ready" << std::endl;
                std::this_thread::sleep_for(std::chrono::seconds(30));
            }
            if (mode == "fail" || mode == "keep")
                throw std::runtime_error("Injected build failure.");
            if (mode == "collision") {
                fs::create_directory(output);
                write_file(output / "sentinel", Bytes{42});
            }
            staging.publish();
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
