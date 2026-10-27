# BioComm-Messknoten (ESP32-S3), ESP-IDF-Projekt. Bauen:
#   idf.py set-target esp32s3 build
# Die CI (Job firmware-esp32) baut es bei jedem Push im offiziellen ESP-IDF-Container.
cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../komponenten")
# Firmware-Version: geht im LAUF_START als firmware_version an den Server.
set(PROJECT_VER "0.2.0")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(omn_knoten)
