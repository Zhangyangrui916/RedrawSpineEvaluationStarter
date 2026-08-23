#include <algorithm>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

std::string requiredValue(int argc, char **argv, const std::string &key) {
    for (int i = 1; i < argc - 1; ++i) {
        if (argv[i] == key) return argv[i + 1];
    }
    throw std::invalid_argument("Missing required argument " + key);
}

}  // namespace

int main(int argc, char **argv) {
    fs::path temporary;
    try {
        const fs::path case_dir = fs::u8path(requiredValue(argc, argv, "--case"));
        const fs::path output_dir = fs::u8path(requiredValue(argc, argv, "--output"));
        const fs::path source_dir = case_dir / "source_attachments";
        if (!fs::is_directory(case_dir) || !fs::is_regular_file(case_dir / "case.json") ||
            !fs::is_directory(source_dir)) {
            throw std::invalid_argument("Case directory is missing case.json or source_attachments");
        }
        if (fs::exists(output_dir)) throw std::invalid_argument("Output directory must not already exist");

        std::vector<fs::path> pages;
        for (const fs::directory_entry &entry : fs::directory_iterator(source_dir)) {
            if (entry.is_regular_file() && entry.path().extension() == ".png") pages.push_back(entry.path());
        }
        std::sort(pages.begin(), pages.end());
        if (pages.empty()) throw std::invalid_argument("Case has no source attachment PNGs");

        const auto suffix = std::chrono::steady_clock::now().time_since_epoch().count();
        temporary = output_dir;
        temporary += ".tmp-" + std::to_string(suffix);
        if (!output_dir.parent_path().empty()) fs::create_directories(output_dir.parent_path());
        fs::create_directories(temporary);
        for (const fs::path &page : pages) fs::copy_file(page, temporary / page.filename());
        fs::rename(temporary, output_dir);

        std::cout << "No-op starter copied " << pages.size() << " source attachment pages to "
                  << output_dir.u8string() << '\n';
        return 0;
    } catch (const std::exception &error) {
        if (!temporary.empty()) {
            std::error_code ignored;
            fs::remove_all(temporary, ignored);
        }
        std::cerr << "redrawspine-reconstruct: " << error.what() << '\n';
        return 1;
    }
}
