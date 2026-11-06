# ESP-IDF-Komponente "omn_treiber": Bausteine der Platine (Register, Umrechnungen,
# Zeitachse) ohne Plattform. Den Bus liefert der Knoten über omn_i2c_t.
# Auf dem PC übersetzt werkzeuge/host_test.py dieselben Quellen direkt, ohne CMake.
idf_component_register(
    SRCS "src/omn_i2c.c"
         "src/omn_ads1115.c"
         "src/omn_ds3231.c"
         "src/omn_max17048.c"
         "src/omn_ds18b20.c"
         "src/omn_zeitachse.c"
    INCLUDE_DIRS "include")
