#pragma once
#include <filesystem>
#include <stdexcept>
#include <string>

namespace talkie {
// A fixed staging name also excludes competing builders for this destination.
// Never adopt or remove a directory left by another build.
class StagingDirectory {
    std::filesystem::path output_, path_;
    bool keep_, published_ = false;

  public:
    StagingDirectory(const std::filesystem::path &output, bool keep)
        : output_(output), path_(output), keep_(keep) {
        path_ += ".building";
        if (std::filesystem::exists(output_))
            throw std::runtime_error("Output already exists. Choose a new folder.");
        std::filesystem::create_directories(output_.parent_path());
        if (!std::filesystem::create_directory(path_))
            throw std::runtime_error(
                "Build staging folder already exists: " + path_.u8string() +
                "\nAnother build may be running. If it was interrupted, move or remove this "
                "folder before retrying, or choose another output folder.");
    }
    StagingDirectory(const StagingDirectory &) = delete;
    StagingDirectory &operator=(const StagingDirectory &) = delete;
    ~StagingDirectory() {
        if (!published_ && !keep_) {
            std::error_code ignored;
            std::filesystem::remove_all(path_, ignored);
        }
    }
    const std::filesystem::path &path() const { return path_; }
    void publish() {
        if (std::filesystem::exists(output_))
            throw std::runtime_error("Output appeared during the build. Choose a new folder.");
        std::filesystem::rename(path_, output_);
        published_ = true;
    }
};
} // namespace talkie
