# ESP-IDF-Komponente "omn_paket" (eingebunden von firmware/knoten über EXTRA_COMPONENT_DIRS).
# Auf dem PC übersetzt werkzeuge/host_test.py dieselben Quellen direkt, ohne CMake.
idf_component_register(
    SRCS "src/omn_paket.c"
         "src/omn_krypto.c"
         "src/omn_selbsttest.c"
         "../../drittanbieter/monocypher/monocypher.c"
         "../../drittanbieter/monocypher/monocypher-ed25519.c"
    INCLUDE_DIRS "include" "../../drittanbieter/monocypher")
