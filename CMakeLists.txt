cmake_minimum_required(VERSION 3.16)
project(boss-sentinel VERSION 2.0.2 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(GTKMM REQUIRED IMPORTED_TARGET gtkmm-4.0)
pkg_check_modules(GLIBMM REQUIRED IMPORTED_TARGET glibmm-2.68)

add_executable(boss-sentinel-bin
  src/main.cpp
  src/app/application.cpp
  src/core/logger.cpp
  src/core/settings.cpp
  src/core/paths.cpp
  src/monitor/engine.cpp
  src/heal/healer.cpp
  src/optimize/optimizer.cpp
  src/ui/main_window.cpp
  src/ui/dialogs.cpp
)

target_include_directories(boss-sentinel-bin PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/src
  ${GTKMM_INCLUDE_DIRS}
)

target_link_libraries(boss-sentinel-bin PRIVATE
  PkgConfig::GTKMM
  PkgConfig::GLIBMM
)

target_compile_options(boss-sentinel-bin PRIVATE -Wall -Wextra -Wno-unused-parameter)

# Install CSS next to binary resources path used at runtime
install(TARGETS boss-sentinel-bin RUNTIME DESTINATION lib/boss-sentinel)
install(FILES src/ui/style.css DESTINATION share/boss-sentinel)
install(PROGRAMS scripts/boss-sentinel DESTINATION bin)
install(PROGRAMS scripts/boss-sentinel-helper DESTINATION libexec/boss-sentinel)
install(FILES data/desktop/org.bosssentinel.BossSentinel.desktop
        DESTINATION share/applications)
install(FILES data/icons/org.bosssentinel.BossSentinel.svg
        DESTINATION share/icons/hicolor/scalable/apps)
install(FILES data/polkit/org.bosssentinel.policy
        DESTINATION share/polkit-1/actions)

# Local build convenience: copy css beside binary in build dir
add_custom_command(TARGET boss-sentinel-bin POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E make_directory $<TARGET_FILE_DIR:boss-sentinel-bin>/share/boss-sentinel
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
          ${CMAKE_SOURCE_DIR}/src/ui/style.css
          $<TARGET_FILE_DIR:boss-sentinel-bin>/share/boss-sentinel/style.css
)
